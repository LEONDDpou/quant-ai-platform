"""AI Agent 服务层 — 多 Agent 协作市场研判。

三个 Agent：
  - MarketMacroAgent   : 宏观环境研判（政策方向、流动性环境、外部冲击）
  - SectorRotationAgent: 行业轮动分析（风格切换、板块强弱、热点题材）
  - StrategyAdvisorAgent: 策略建议（仓位建议、行业配置、策略推荐、风险提示）

设计要点：
  - 复用 llm_service._chat + _extract_json 底层能力
  - 每个 Agent 独立调用 LLM，可并发
  - 聚合三个 Agent 的结果生成最终研判
  - 输出格式对齐用户 Mockup：大盘判断 + 风险星级 + 机会板块 + 操作建议 + AI综合评分
"""

import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.llm_service import _chat, _extract_json, is_llm_enabled, LLM_MODEL

# 研判缓存（10min TTL）：综合研判属「每日级」产出，避免每次都跑 3 个 LLM Agent；
# 同时也让 dashboard/v2 在 30s 整体缓存过期后的冷启动跳过 LLM，大幅提速。
JUDGMENT_CACHE: dict = {"data": None, "ts": 0.0, "model": None}
JUDGMENT_TTL = 600  # 10 分钟

# ============================================================
# 数据聚合
# ============================================================
def _build_agent_context() -> dict:
    """为 Agent 构建市场上下文数据。"""
    from app.services import data_provider as dp
    from app.services.market_dynamics_service import get_capital_flow, get_sector_rankings
    from app.services.market_temperature_service import get_market_temperature

    indices = dp.get_indices()
    news = dp.get_news()

    # 指数摘要
    idx_list = [
        {"name": i["name"], "value": i["value"], "changePct": i["changePct"]}
        for i in indices
    ]

    # 新闻标题
    news_list = [
        {"title": n["title"], "sentiment": n["sentiment"]}
        for n in news[:20]
    ]

    # 资金流向
    try:
        cap = get_capital_flow()
    except Exception:
        cap = {"mainNetFlow": 0, "mainNetFlow5d": 0, "mainNetFlow20d": 0}

    # 板块排名
    try:
        sectors = get_sector_rankings(15)
    except Exception:
        sectors = []

    # 市场温度
    try:
        temp = get_market_temperature()
    except Exception:
        temp = {"score": 50, "riskLevel": "medium", "riskLabel": "正常"}

    return {
        "date": datetime.date.today().isoformat(),
        "time": time.strftime("%H:%M:%S"),
        "indices": idx_list,
        "news": news_list,
        "capitalFlow": {
            "mainNetFlow": cap.get("mainNetFlow", 0),
            "mainNetFlow5d": cap.get("mainNetFlow5d", 0),
        },
        "sectors": [
            {"name": s["name"], "chg5d": s["chg5d"], "chg20d": s["chg20d"]}
            for s in sectors
        ],
        "marketTemperature": {
            "score": temp.get("score", 50),
            "level": temp.get("riskLevel", "medium"),
            "label": temp.get("riskLabel", "正常"),
        },
    }


# ============================================================
# Agent 1: 宏观研判
# ============================================================
def _run_macro_agent(context: dict) -> dict | None:
    """宏观环境研判 Agent。"""
    system = (
        "你是一名资深宏观策略研究员，服务于A股量化交易平台。"
        "你必须【只】返回一个 JSON 对象。\n"
        "JSON 结构：\n"
        "{\n"
        '  "environment": "强牛市" | "震荡偏强" | "震荡" | "震荡偏弱" | "弱势",\n'
        '  "policyDirection": "宽松" | "中性" | "收紧",\n'
        '  "liquidity": "充裕" | "正常" | "偏紧",\n'
        '  "externalShocks": ["外部冲击因素1", "..."],\n'
        '  "macroSummary": "宏观环境总体判断（中文，3-5句）"\n'
        "}\n"
        "要求：基于提供的真实数据推理，客观中立，不编造数据。"
    )
    user = f"市场数据：\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    content = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.4,
    )
    return _extract_json(content) if content else None


# ============================================================
# Agent 2: 行业轮动
# ============================================================
def _run_sector_agent(context: dict) -> dict | None:
    """行业轮动分析 Agent。"""
    system = (
        "你是一名资深行业分析师，专注A股行业轮动与风格切换研究。"
        "你必须【只】返回一个 JSON 对象。\n"
        "JSON 结构：\n"
        "{\n"
        '  "style": "大盘价值" | "大盘成长" | "小盘价值" | "小盘成长",\n'
        '  "strongSectors": ["强势板块1","强势板块2","强势板块3"],\n'
        '  "weakSectors": ["弱势板块1","弱势板块2","弱势板块3"],\n'
        '  "hotThemes": ["热点题材1","热点题材2","热点题材3"],\n'
        '  "rotationSignal": "风格切换" | "强者恒强" | "超跌反弹" | "轮动加快",\n'
        '  "sectorSummary": "行业轮动判断（中文，3-5句）"\n'
        "}\n"
        "要求：基于提供的真实板块涨跌数据推理，客观中立。"
    )
    user = f"行业板块数据：\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    content = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,
    )
    return _extract_json(content) if content else None


# ============================================================
# Agent 3: 策略建议
# ============================================================
def _run_strategy_agent(context: dict) -> dict | None:
    """策略建议 Agent。"""
    system = (
        "你是一名资深量化策略师，负责生成A股交易策略建议。"
        "你必须【只】返回一个 JSON 对象。\n"
        "JSON 结构：\n"
        "{\n"
        '  "positionAdvice": "重仓(80-100%)" | "中等仓位(50-80%)" | "轻仓(30-50%)" | "防御仓位(0-30%)",\n'
        '  "sectorAllocation": [{"sector":"行业名","weight":权重整数}],\n'
        '  "recommendedStrategies": ["推荐策略1","推荐策略2"],\n'
        '  "riskStars": 1-5的整数,\n'
        '  "keyRisks": ["风险1","风险2","风险3"],\n'
        '  "actionPlan": "具体操作计划（中文，3-5句）"\n'
        "}\n"
        "要求：基于市场温度、资金流向、板块轮动等真实数据，给出量化视角的策略建议。保守偏稳健。"
    )
    user = f"市场综合数据：\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    content = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.4,
    )
    return _extract_json(content) if content else None


# ============================================================
# 公开接口
# ============================================================
def generate_market_judgment(force: bool = False) -> dict:
    """多 Agent 协作生成今日市场综合研判。"""
    # 命中缓存直接返回，避免每次都跑 3 个 LLM Agent（也加速 dashboard 冷启动）
    now = time.time()
    if (
        not force
        and JUDGMENT_CACHE["data"] is not None
        and JUDGMENT_CACHE["model"] == LLM_MODEL
        and (now - JUDGMENT_CACHE["ts"]) < JUDGMENT_TTL
    ):
        return JUDGMENT_CACHE["data"]
    context = _build_agent_context()

    if not is_llm_enabled():
        return _fallback_judgment(context)

    # 并发运行三个 Agent
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_run_macro_agent, context): "macro",
            pool.submit(_run_sector_agent, context): "sector",
            pool.submit(_run_strategy_agent, context): "strategy",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result(timeout=60)
            except Exception as e:
                print(f"[AI-Agent] {name} agent failed: {e}")
                results[name] = None

    # 聚合结果
    macro = results.get("macro") or {}
    sector = results.get("sector") or {}
    strategy = results.get("strategy") or {}

    # AI综合评分（0-100）
    ai_score = _calc_ai_score(context, strategy)

    judgment = {
        "date": context["date"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "marketTrend": macro.get("environment", "震荡"),
        "marketSummary": macro.get("macroSummary", ""),
        "policyDirection": macro.get("policyDirection", "中性"),
        "liquidity": macro.get("liquidity", "正常"),
        "externalShocks": macro.get("externalShocks", []),
        "style": sector.get("style", "—"),
        "strongSectors": sector.get("strongSectors", []),
        "weakSectors": sector.get("weakSectors", []),
        "hotThemes": sector.get("hotThemes", []),
        "rotationSignal": sector.get("rotationSignal", "—"),
        "sectorSummary": sector.get("sectorSummary", ""),
        "positionAdvice": strategy.get("positionAdvice", "中等仓位(50-80%)"),
        "sectorAllocation": strategy.get("sectorAllocation", []),
        "recommendedStrategies": strategy.get("recommendedStrategies", []),
        "riskStars": int(strategy.get("riskStars", 3)),
        "keyRisks": strategy.get("keyRisks", []),
        "actionPlan": strategy.get("actionPlan", ""),
        "aiScore": ai_score,
        "temperatureScore": context["marketTemperature"]["score"],
        "model": LLM_MODEL,
        "generatedBy": "multi-agent",
    }

    # 持久化
    _save_judgment(judgment)
    # 写入缓存，供后续请求直接命中
    JUDGMENT_CACHE["data"] = judgment
    JUDGMENT_CACHE["ts"] = time.time()
    JUDGMENT_CACHE["model"] = LLM_MODEL
    return judgment


def _calc_ai_score(context: dict, strategy: dict) -> int:
    """计算 AI 综合评分（0-100），结合温度 + 策略信号。"""
    base = context["marketTemperature"]["score"]
    risk_stars = int(strategy.get("riskStars", 3))
    # 风险星级越低，AI评分上调
    risk_adjust = (3 - risk_stars) * 5
    score = int(base + risk_adjust)
    return max(0, min(100, score))


def _fallback_judgment(context: dict) -> dict:
    """LLM未配置时的规则合成研判。"""
    temp_score = context["marketTemperature"]["score"]
    if temp_score < 30:
        trend = "弱势"
        advice = "防御仓位(0-30%)"
        risk = 4
    elif temp_score < 50:
        trend = "震荡偏弱"
        advice = "轻仓(30-50%)"
        risk = 3
    elif temp_score < 70:
        trend = "震荡"
        advice = "中等仓位(50-80%)"
        risk = 3
    elif temp_score < 85:
        trend = "震荡偏强"
        advice = "中等仓位(50-80%)"
        risk = 2
    else:
        trend = "强牛市"
        advice = "重仓(80-100%)"
        risk = 1

    return {
        "date": context["date"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "marketTrend": trend,
        "marketSummary": f"市场温度 {temp_score}/100，{context['marketTemperature']['label']}区间。",
        "policyDirection": "—",
        "liquidity": "—",
        "externalShocks": [],
        "style": "—",
        "strongSectors": [],
        "weakSectors": [],
        "hotThemes": [],
        "rotationSignal": "—",
        "sectorSummary": "",
        "positionAdvice": advice,
        "sectorAllocation": [],
        "recommendedStrategies": [],
        "riskStars": risk,
        "keyRisks": ["数据不完整，无法详细分析"],
        "actionPlan": f"根据市场温度 {temp_score} 分，建议{advice}。等待LLM接入后提供更详细分析。",
        "aiScore": int(temp_score),
        "temperatureScore": temp_score,
        "model": "rules",
        "generatedBy": "fallback",
    }


def _save_judgment(judgment: dict):
    """AI 市场研判持久化。"""
    try:
        from app.db.database import SessionLocal
        from app.db.models import AIMarketJudgment
        db = SessionLocal()
        try:
            from datetime import date
            today = date.today()
            existing = db.query(AIMarketJudgment).filter(AIMarketJudgment.date == today).first()
            if existing:
                for key, val in judgment.items():
                    if hasattr(existing, key) and key not in ("id", "created_at"):
                        setattr(existing, key, val)
            else:
                db.add(AIMarketJudgment(
                    date=today,
                    market_trend=judgment["marketTrend"],
                    risk_stars=judgment["riskStars"],
                    opportunities=judgment.get("strongSectors", []),
                    advice=judgment.get("actionPlan", ""),
                    ai_score=judgment["aiScore"],
                    dimensions={
                        "macro": judgment.get("marketSummary", ""),
                        "sector": judgment.get("sectorSummary", ""),
                        "strategy": judgment.get("actionPlan", ""),
                    },
                    buy_probability=f"{'高' if judgment['aiScore'] > 65 else '中' if judgment['aiScore'] > 40 else '低'}",
                    generated_by=judgment.get("generatedBy", "unknown"),
                    model=judgment.get("model", "unknown"),
                ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[AI-Agent] DB save failed: {e}")


def analyze_sector(topic: str = "") -> dict:
    """行业板块 AI 分析。"""
    context = _build_agent_context()
    system = (
        "你是一名行业研究员。针对用户问题做板块分析。"
        "必须【只】返回 JSON：\n"
        "{\n"
        '  "analysis": "分析结论（中文，3-5句）",\n'
        '  "bullishSectors": ["看好的板块"],\n'
        '  "bearishSectors": ["看空的板块"],\n'
        '  "themes": ["当前主题"],\n'
        '  "outlook": "展望"\n'
        "}\n"
    )
    user = f"市场数据：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n分析问题：{topic or '当前A股行业轮动与板块机会分析'}"
    content = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,
    )
    return _extract_json(content) if content else {"analysis": "LLM未配置或无数据", "bullishSectors": [], "bearishSectors": [], "themes": [], "outlook": ""}
