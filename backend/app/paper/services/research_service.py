"""研究员 Agent 服务层（#182 核心）。

职责：把「因子挖掘 → 策略生成 → 持久化 → 回测贯通」串成一个可编排的智能体。

设计要点：
- 双轨生成：LLM 模式（调用 llm_service 大模型，需配置 LLM_API_KEY）与
  规则确定性模式（本地指标计算，零外网依赖）。LLM 不可用或解析失败时
  自动回退规则模式，保证永远有产出。
- 因子挖掘：对给定股票宇宙拉取真实日 K 线，本地计算动量 / 波动率 /
  反转 / RSI / 量能 等因子，按宇宙聚合为「因子结论」。
- 策略生成：把因子信号映射成「事件驱动回测引擎（M181）」兼容的
  EventRule 规则（入场 / 出场 / 全局风控），产出可一键回测的策略想法。
- 回测贯通：backtest_idea() 直接复用 BacktestService.run_event()，
  把回测 run_id 关联回策略想法，形成「研究 → 回测」闭环。
"""
import datetime
from typing import Optional

from app.paper.domain_models import (
    PaperResearchSession,
    PaperFactorFinding,
    PaperStrategyIdea,
)
from app.paper.errors import PaperError
from app.paper.schemas import (
    RunResearchRequest,
    RunResearchResponse,
    PaperResearchSessionResponse,
    PaperFactorFindingResponse,
    PaperStrategyIdeaResponse,
)
from app.paper.repositories.research_repo import (
    ResearchSessionRepository,
    FactorFindingRepository,
    StrategyIdeaRepository,
)
from app.services import data_provider as dp
from app.services import llm_service as llm

# 默认研究宇宙（与 llm_service.WATCHLIST 一致，作为未指定时的兜底）
DEFAULT_UNIVERSE = ["600519", "300750", "601318", "000858", "600036"]

# 事件驱动回测引擎支持的触发类型（用于 LLM 产出校验，防止越界）
SUPPORTED_KINDS = {
    "ma_cross", "price_breakout", "rsi",
    "drawdown_stop", "take_profit", "hold_days",
}


# ============================================================
# 本地指标（确定性，不依赖外网）
# ============================================================
def _sma(values: list, n: int) -> float:
    """简单移动平均；序列不足返回末值。"""
    if not values:
        return 0.0
    if len(values) < n:
        return float(sum(values) / len(values))
    return float(sum(values[-n:]) / n)


def _stdev(values: list) -> float:
    """样本标准差。"""
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def _rsi(closes: list, n: int = 14) -> float:
    """相对强弱指标(0-100)。"""
    if len(closes) < n + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = _sma(gains[-n:], n)
    al = _sma(losses[-n:], n)
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return float(100 - 100 / (1 + rs))


def _stock_factor_signals(code: str) -> Optional[dict]:
    """拉取单只标的 K 线并计算因子信号；失败（含无数据）返回 None。"""
    try:
        kline = dp.get_stock_kline(code, period="day", limit=120)
    except Exception:
        return None
    if not kline or len(kline) < 25:
        return None
    closes = [float(k.get("close", 0.0)) for k in kline if k.get("close")]
    vols = [float(k.get("volume", 0.0)) for k in kline if k.get("close")]
    if len(closes) < 25:
        return None

    # 日收益率序列
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes)) if closes[i - 1]]

    mom20 = (closes[-1] / closes[-21] - 1.0) if len(closes) > 21 else 0.0
    mom60 = (closes[-1] / closes[-61] - 1.0) if len(closes) > 61 else mom20
    vol20 = _stdev(rets[-20:]) * (252 ** 0.5) if len(rets) >= 20 else 0.0
    rev5 = (closes[-1] / closes[-6] - 1.0) if len(closes) > 6 else 0.0
    rsi14 = _rsi(closes, 14)
    vma5 = _sma(vols[-5:], 5)
    vma20 = _sma(vols[-20:], 20)
    vol_trend = (vma5 / vma20 - 1.0) if vma20 > 0 else 0.0

    return {
        "code": code,
        "momentum20": mom20,
        "momentum60": mom60,
        "volatility20": vol20,
        "reversal5": rev5,
        "rsi14": rsi14,
        "volumeTrend": vol_trend,
    }


# ============================================================
# 服务主体
# ============================================================
class ResearcherAgentService:
    """研究员 Agent：因子挖掘 + 策略生成的编排智能体。"""

    def __init__(self):
        self.session_repo = ResearchSessionRepository()
        self.factor_repo = FactorFindingRepository()
        self.idea_repo = StrategyIdeaRepository()

    # —— 对外：触发一次研究 ——
    def run_research(self, req: RunResearchRequest) -> RunResearchResponse:
        universe = list(req.universe) if req.universe else list(DEFAULT_UNIVERSE)
        # 归一化代码（统一成纯数字，便于 K 线拉取）
        universe = [dp.to_westock_code(c) for c in universe]
        use_llm = bool(req.useLlm) and llm.is_llm_enabled()

        # 1) 挖掘因子（双轨）
        if use_llm:
            factors = self._mine_factors_llm(universe) or self._mine_factors_rule_based(universe)
        else:
            factors = self._mine_factors_rule_based(universe)

        # 2) 生成策略想法（双轨）
        if use_llm:
            ideas = self._generate_strategies_llm(factors, universe, req.maxIdeas) \
                or self._generate_strategies_rule_based(factors, universe, req.maxIdeas)
        else:
            ideas = self._generate_strategies_rule_based(factors, universe, req.maxIdeas)

        # 3) 落库：会话 + 因子 + 策略
        session = self.session_repo.add(PaperResearchSession(
            account_id=req.accountId,
            universe=universe,
            mode="llm" if use_llm else "rule",
            model=llm.LLM_MODEL if use_llm else "rule-based",
            summary=self._build_summary(factors, ideas),
            status="completed",
        ))
        for f in factors:
            self.factor_repo.add(PaperFactorFinding(session_id=session.id, **f))
        for idea in ideas:
            self.idea_repo.add(PaperStrategyIdea(session_id=session.id, **idea))

        resp = self._session_to_resp(session)
        return RunResearchResponse(
            session=resp,
            factorCount=len(factors),
            ideaCount=len(ideas),
        )

    # —— 因子挖掘：规则确定性 ——
    def _mine_factors_rule_based(self, universe: list) -> list:
        """逐标的计算因子信号，按宇宙聚合为因子结论。"""
        sigs = []
        for code in universe:
            s = _stock_factor_signals(code)
            if s:
                sigs.append(s)
        if not sigs:
            return []

        def _avg(key):
            return sum(x[key] for x in sigs) / len(sigs)

        mom20 = _avg("momentum20")
        mom60 = _avg("momentum60")
        vol20 = _avg("volatility20")
        rev5 = _avg("reversal5")
        rsi14 = _avg("rsi14")
        vt = _avg("volumeTrend")

        # 评分：把因子原始值映射到 0-100（越大表示「越偏该方向」）
        def _score_pos(v, scale):
            return max(0.0, min(100.0, 50.0 + v / scale * 50.0))

        factors = [
            {
                "name": "20日动量",
                "factor_type": "momentum",
                "description": "近20个交易日累计涨幅，衡量中期趋势强度。",
                "direction": "long" if mom20 > 0 else "short",
                "score": _score_pos(mom20, 0.20),
                "detail": {"avg": round(mom20, 4), "perStock": {s["code"]: round(s["momentum20"], 4) for s in sigs}},
            },
            {
                "name": "60日动量",
                "factor_type": "momentum",
                "description": "近60个交易日累计涨幅，衡量长期趋势。",
                "direction": "long" if mom60 > 0 else "short",
                "score": _score_pos(mom60, 0.40),
                "detail": {"avg": round(mom60, 4), "perStock": {s["code"]: round(s["momentum60"], 4) for s in sigs}},
            },
            {
                "name": "20日年化波动率",
                "factor_type": "volatility",
                "description": "近20日日收益率年化标准差，衡量风险水平。",
                "direction": "short" if vol20 > 0.35 else "neutral",
                "score": _score_pos(vol20, 0.50),
                "detail": {"avg": round(vol20, 4), "perStock": {s["code"]: round(s["volatility20"], 4) for s in sigs}},
            },
            {
                "name": "5日反转",
                "factor_type": "reversal",
                "description": "近5个交易日涨跌幅，捕捉短期超买/超卖后的均值回归。",
                "direction": "long" if rev5 < 0 else "short",
                "score": _score_pos(-rev5, 0.10),
                "detail": {"avg": round(rev5, 4), "perStock": {s["code"]: round(s["reversal5"], 4) for s in sigs}},
            },
            {
                "name": "RSI(14)",
                "factor_type": "rsi",
                "description": "相对强弱指标，>70 超买、<30 超卖。",
                "direction": "long" if rsi14 < 45 else ("short" if rsi14 > 55 else "neutral"),
                "score": _score_pos(50 - rsi14, 50),
                "detail": {"avg": round(rsi14, 2), "perStock": {s["code"]: round(s["rsi14"], 2) for s in sigs}},
            },
            {
                "name": "量能趋势",
                "factor_type": "volume",
                "description": "近5日成交量相对近20日均量变化，衡量资金关注度。",
                "direction": "long" if vt > 0 else "neutral",
                "score": _score_pos(vt, 0.50),
                "detail": {"avg": round(vt, 4), "perStock": {s["code"]: round(s["volumeTrend"], 4) for s in sigs}},
            },
        ]
        return factors

    # —— 因子挖掘：LLM 模式 ——
    def _mine_factors_llm(self, universe: list) -> Optional[list]:
        """用大模型基于真实行情摘要提出因子结论；失败返回 None。"""
        # 先用规则算出真实数值，作为 LLM 的上下文（避免编造）
        base = self._mine_factors_rule_based(universe)
        if not base:
            return None
        ctx = {f["name"]: {"direction": f["direction"], "score": round(f["score"], 1),
                           "detail": f["detail"].get("avg")} for f in base}
        system = (
            "你是量化研究员。基于给定的真实因子数值，提炼出本宇宙的「因子结论」。"
            "只返回 JSON 数组，每项："
            '{"name":"因子名","factor_type":"momentum|volatility|reversal|rsi|volume|quality",'
            '"description":"一句话说明","direction":"long|short|neutral","score":0-100}。'
            "不要解释，数组长度 3-6。"
        )
        user = f"股票宇宙：{universe}\n真实因子数值：\n{ctx}"
        content = llm._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.4,
        )
        data = llm._extract_json(content) if content else None
        if not isinstance(data, list):
            return None
        out = []
        for d in data[:6]:
            if not isinstance(d, dict):
                continue
            out.append({
                "name": str(d.get("name", "未命名因子"))[:50],
                "factor_type": str(d.get("factor_type", "quality"))[:30],
                "description": str(d.get("description", "")),
                "direction": str(d.get("direction", "neutral"))[:10],
                "score": max(0.0, min(100.0, float(d.get("score", 50) or 50))),
                "detail": {},
            })
        return out or None

    # —— 策略生成：规则确定性 ——
    def _generate_strategies_rule_based(self, factors: list, universe: list, max_ideas: int) -> list:
        """由因子信号映射成事件驱动策略想法。"""
        by_type = {f["factor_type"]: f for f in factors}
        by_name = {f["name"]: f for f in factors}

        mom = by_name.get("20日动量", {}).get("detail", {}).get("avg", 0.0)
        rsi = by_name.get("RSI(14)", {}).get("detail", {}).get("avg", 50.0)
        vol = by_name.get("20日年化波动率", {}).get("detail", {}).get("avg", 0.25)
        vt = by_name.get("量能趋势", {}).get("detail", {}).get("avg", 0.0)

        ideas = []

        # 基线：双均线 + 全局风控（任何市场都可用）
        stop = 6.0 if vol > 0.4 else 8.0
        take = 20.0 if vol > 0.4 else 25.0
        ideas.append({
            "name": "双均线趋势(MA5/MA20)+风控",
            "description": "经典双均线交叉：快线上穿慢线买入、下穿卖出；叠加全局止损/止盈。",
            "universe": universe,
            "entry_rules": [{"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}}],
            "exit_rules": [{"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}}],
            "risk": {"stopLoss": stop, "takeProfit": take},
            "logic": "MA5 上穿 MA20 视为趋势启动买入；MA5 下穿 MA20 视为趋势结束卖出；"
                     f"持仓期间若回撤超 {stop}% 止损、盈利超 {take}% 止盈。",
            "expected": "适合中等级趋势市；震荡市易频繁假突破。",
        })

        # 动量增强：若中期动量偏多，叠加突破跟随
        if mom > 0.03:
            ideas.append({
                "name": "动量突破跟随",
                "description": "在中期动量偏多背景下，价格创20日新高时顺势介入。",
                "universe": universe,
                "entry_rules": [{"side": "entry", "kind": "price_breakout", "params": {"window": 20}}],
                "exit_rules": [{"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}}],
                "risk": {"stopLoss": stop, "takeProfit": take},
                "logic": "收盘价突破过去20日最高价买入；趋势反转(MA5下穿MA20)卖出；"
                         f"回撤超 {stop}% 止损。",
                "expected": "捕捉主升浪；需配合量能确认以降低假突破。",
            })

        # 反转增强：若 RSI 偏极端，叠加 RSI 反转
        if rsi < 45 or rsi > 55:
            buy_below = 30 if rsi < 45 else 45
            sell_above = 70 if rsi < 45 else 60
            ideas.append({
                "name": "RSI极端反转",
                "description": f"RSI(14)均值为{rsi:.0f}，处于{'超卖' if rsi < 45 else '超买'}区，做均值回归。",
                "universe": universe,
                "entry_rules": [{"side": "entry", "kind": "rsi", "params": {"period": 14, "threshold": buy_below, "direction": "below"}}],
                "exit_rules": [{"side": "exit", "kind": "rsi", "params": {"period": 14, "threshold": sell_above, "direction": "above"}}],
                "risk": {"stopLoss": stop, "takeProfit": take},
                "logic": f"RSI(14)跌破{buy_below}买入（超卖），升破{sell_above}卖出（超买）；"
                         f"回撤超 {stop}% 止损。",
                "expected": "适合震荡/反转市；单边趋势市易过早离场。",
            })

        # 量能增强：若量能趋势走升，叠加突破
        if vt > 0.1 and len(ideas) < max_ideas:
            ideas.append({
                "name": "放量突破",
                "description": "量能趋势走升时，价格突破20日高点顺势介入。",
                "universe": universe,
                "entry_rules": [{"side": "entry", "kind": "price_breakout", "params": {"window": 20}}],
                "exit_rules": [{"side": "exit", "kind": "hold_days", "params": {"days": 10}}],
                "risk": {"stopLoss": stop, "takeProfit": take},
                "logic": "量能放大(5日均量>20日均量)且价格突破20日高点买入；持有至多10日卖出；"
                         f"回撤超 {stop}% 止损。",
                "expected": "捕捉放量启动的短线机会；持仓周期短。",
            })

        return ideas[:max_ideas]

    # —— 策略生成：LLM 模式 ——
    def _generate_strategies_llm(self, factors: list, universe: list, max_ideas: int) -> Optional[list]:
        """用大模型基于因子结论设计事件驱动策略；失败返回 None。"""
        ctx = [{"name": f["name"], "direction": f["direction"], "score": round(f["score"], 1),
                "type": f["factor_type"]} for f in factors]
        system = (
            "你是量化策略师。基于因子结论，设计最多 %d 个「事件驱动」交易策略。"
            "每个策略必须是 JSON：\n"
            '{"name":"策略名","description":"一句话","universe":[],'
            '"entry_rules":[{"side":"entry","kind":"ma_cross|price_breakout|rsi|hold_days","params":{}}],'
            '"exit_rules":[{"side":"exit","kind":"ma_cross|price_breakout|rsi|drawdown_stop|take_profit|hold_days","params":{}}],'
            '"risk":{"stopLoss":数值,"takeProfit":数值},"logic":"逻辑","expected":"预期"}。\n'
            "kind 只能从上述枚举中选；params 须合法（ma_cross:{fast,slow}，price_breakout:{window}，"
            "rsi:{period,threshold,direction}，drawdown_stop:{pct}，take_profit:{pct}，hold_days:{days}）。"
            "只返回 JSON 数组，不要解释。"
        ) % max_ideas
        user = f"股票宇宙：{universe}\n因子结论：\n{ctx}"
        content = llm._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.5,
        )
        data = llm._extract_json(content) if content else None
        if not isinstance(data, list):
            return None
        out = []
        for d in data[:max_ideas]:
            if not isinstance(d, dict):
                continue
            entry = [r for r in d.get("entry_rules", []) if isinstance(r, dict) and r.get("kind") in SUPPORTED_KINDS]
            exit = [r for r in d.get("exit_rules", []) if isinstance(r, dict) and r.get("kind") in SUPPORTED_KINDS]
            if not entry or not exit:
                continue
            risk = d.get("risk", {}) or {}
            out.append({
                "name": str(d.get("name", "LLM策略"))[:100],
                "description": str(d.get("description", "")),
                "universe": universe,
                "entry_rules": [{"side": "entry", **r} for r in entry],
                "exit_rules": [{"side": "exit", **r} for r in exit],
                "risk": {"stopLoss": float(risk.get("stopLoss", 8.0) or 8.0),
                         "takeProfit": float(risk.get("takeProfit", 25.0) or 25.0)},
                "logic": str(d.get("logic", "")),
                "expected": str(d.get("expected", "")),
            })
        return out or None

    # —— 总结 ——
    def _build_summary(self, factors: list, ideas: list) -> str:
        if not factors:
            return "本次研究未获取到有效行情数据，未生成因子结论。"
        top = sorted(factors, key=lambda f: f["score"], reverse=True)[:3]
        top_str = "、".join(f"{f['name']}({'偏多' if f['direction']=='long' else '偏空' if f['direction']=='short' else '中性'})" for f in top)
        return f"挖掘因子 {len(factors)} 个，主导信号：{top_str}；生成策略想法 {len(ideas)} 个。"

    # —— 查询 ——
    def list_sessions(self, account_id: Optional[int] = None, limit: int = 50) -> list:
        sessions = self.session_repo.list_sessions(account_id, limit)
        return [self._session_to_resp(s) for s in sessions]

    def get_session(self, session_id: int) -> PaperResearchSessionResponse:
        session = self.session_repo.get_session(session_id)
        if not session:
            raise PaperError(f"研究会话不存在: {session_id}")
        return self._session_to_resp(session)

    def list_ideas(self, account_id: Optional[int] = None, limit: int = 100) -> list:
        ideas = self.idea_repo.list_ideas(account_id, limit)
        return [self._idea_to_resp(i) for i in ideas]

    def get_idea(self, idea_id: int) -> PaperStrategyIdeaResponse:
        idea = self.idea_repo.get_idea(idea_id)
        if not idea:
            raise PaperError(f"策略想法不存在: {idea_id}")
        return self._idea_to_resp(idea)

    def delete_idea(self, idea_id: int) -> bool:
        return self.idea_repo.delete_idea(idea_id)

    # —— 回测贯通（复用 M181 事件驱动回测）——
    def backtest_idea(self, idea_id: int, account_id: Optional[int] = None):
        from app.paper.schemas import RunEventBacktestRequest
        from app.paper.services.backtest_service import BacktestService

        idea = self.idea_repo.get_idea(idea_id)
        if not idea:
            raise PaperError(f"策略想法不存在: {idea_id}")
        if not idea.universe:
            raise PaperError("该策略想法缺少适用标的，无法回测")

        req = RunEventBacktestRequest(
            strategyName=idea.name or "研究员策略",
            universe=list(idea.universe),
            rules=(idea.entry_rules or []) + (idea.exit_rules or []),
            risk=idea.risk or {},
            accountId=account_id or idea.account_id,
        )
        bt = BacktestService()
        resp = bt.run_event(req)
        self.idea_repo.mark_backtested(idea.id, resp.id)
        return resp

    # —— 响应转换 ——
    def _session_to_resp(self, session: PaperResearchSession) -> PaperResearchSessionResponse:
        factors = self.factor_repo.list_by_session(session.id)
        idea_objs = self._ideas_by_session(session.id)
        return PaperResearchSessionResponse(
            id=session.id,
            accountId=session.account_id,
            universe=session.universe or [],
            mode=session.mode or "rule",
            model=session.model or "rule-based",
            summary=session.summary or "",
            status=session.status or "completed",
            factors=[self._factor_to_resp(f) for f in factors],
            ideas=[self._idea_to_resp(i) for i in idea_objs],
            createdAt=session.created_at.isoformat() if session.created_at else "",
        )

    def _ideas_by_session(self, session_id: int) -> list:
        with self.idea_repo._session() as db:
            from app.paper.domain_models import PaperStrategyIdea
            return (
                db.query(PaperStrategyIdea)
                .filter(PaperStrategyIdea.session_id == session_id)
                .order_by(PaperStrategyIdea.id.asc())
                .all()
            )

    def _factor_to_resp(self, f: PaperFactorFinding) -> PaperFactorFindingResponse:
        return PaperFactorFindingResponse(
            id=f.id,
            sessionId=f.session_id,
            name=f.name or "",
            factorType=f.factor_type or "",
            description=f.description or "",
            direction=f.direction or "neutral",
            score=float(f.score or 0.0),
            detail=f.detail or {},
            createdAt=f.created_at.isoformat() if f.created_at else "",
        )

    def _idea_to_resp(self, i: PaperStrategyIdea) -> PaperStrategyIdeaResponse:
        return PaperStrategyIdeaResponse(
            id=i.id,
            sessionId=i.session_id,
            accountId=i.account_id,
            name=i.name or "",
            description=i.description or "",
            universe=i.universe or [],
            entryRules=i.entry_rules or [],
            exitRules=i.exit_rules or [],
            risk=i.risk or {},
            logic=i.logic or "",
            expected=i.expected or "",
            backtestRunId=i.backtest_run_id,
            backtested=bool(i.backtested),
            createdAt=i.created_at.isoformat() if i.created_at else "",
        )
