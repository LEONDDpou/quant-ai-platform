"""AI 选股分析报告服务

串联四条能力，构成「AI 选股分析报告系统」：
1. screen       —— 调 westock-tool 条件选股（支持 A/港股/美股）
2. analyze_logic—— 调 LLM 输出选股逻辑分析（数据来源 / 分析维度 / 推荐理由），含规则兜底
3. run_backtests—— 复用 backtest_engine 对入选股票做回测
4. attribute    —— 调 LLM 基于回测汇总做成败归因（盈利→成功逻辑；亏损→失败理由）

所有 AI 输出均为「模型驱动的研究结论」，明确标注 llmEnabled，绝不表达确定性买卖指令。
"""
import json
import re
from typing import Optional

from app.services import westock_tool_client as wt
from app.services import backtest_engine as be
from app.services import llm_service as llm


# --------------------------------------------------------------------------
# 工具：鲁棒 JSON 提取（兼容 ```json 包裹与前后多余文本）
# --------------------------------------------------------------------------
def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    # 优先提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 退而求其次：找第一个 { 到最后一个 }
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s : e + 1])
        except Exception:
            return None
    return None


# --------------------------------------------------------------------------
# 1) 条件选股
# --------------------------------------------------------------------------
def screen(market: str, expression: str, limit: int = 20) -> list[dict]:
    """返回 [{code, name}, ...]，code 为 westock 格式。"""
    if not expression or not expression.strip():
        raise ValueError("选股表达式不能为空")
    return wt.run_filter(expression.strip(), market=market, limit=max(1, min(limit, 100)))


# --------------------------------------------------------------------------
# 2) 选股逻辑分析（LLM）
# --------------------------------------------------------------------------
_LOGIC_SYSTEM = (
    "你是一名专业的量化选股分析师，服务于智能交易终端的专业用户。"
    "根据用户给出的选股市场与筛选条件，输出结构化的「选股逻辑分析」报告，"
    "必须严格只输出如下 JSON（不要任何额外文字）：\n"
    "{\n"
    '  "summary": "一句话总结本次选股思路",\n'
    '  "dataSources": ["用到的数据维度，如 行情/估值/财务/资金流向/技术形态"],\n'
    '  "dimensions": ["分析维度，如 估值安全性/盈利质量/价格动量/资金关注度"],\n'
    '  "reasons": ["针对该条件的推荐理由，2-4 条"]\n'
    "}\n"
    "约束：仅基于用户给出的条件做逻辑推演，不要编造具体个股表现数据；"
    "明确这是基于规则的逻辑分析，不构成投资建议。"
)


def analyze_logic(market: str, expression: str, candidates: list[dict]) -> dict:
    """返回 {summary, dataSources, dimensions, reasons, llmEnabled}。"""
    names = "、".join(f"{c['name']}({c['code']})" for c in candidates[:12])
    if len(candidates) > 12:
        names += f" 等共 {len(candidates)} 只"
    market_label = {"a": "A股沪深", "hk": "港股", "us": "美股"}.get((market or "a").lower(), "A股")

    user_msg = (
        f"市场：{market_label}\n"
        f"筛选条件表达式：{expression}\n"
        f"初步入选标的（{len(candidates)} 只，含名称与代码）：{names}\n"
        "请输出选股逻辑分析。"
    )

    if not llm.is_llm_enabled():
        return {
            "summary": f"基于条件 {expression} 在{market_label}完成初筛，共入选 {len(candidates)} 只标的。",
            "dataSources": ["行情数据", "估值/财务因子（腾讯自选股）", "技术形态指标"],
            "dimensions": ["估值安全性", "盈利质量", "价格动量", "资金关注度"],
            "reasons": [
                "条件表达式显式约束了估值与盈利门槛，过滤掉高估值与亏损标的。",
                "入选标的均通过硬性指标筛选，具备量化可解释性。",
                "后续建议结合回测报告与成败归因验证条件有效性。",
            ],
            "llmEnabled": False,
            "model": "rule-based",
        }

    try:
        reply = llm.chat(
            [{"role": "system", "content": _LOGIC_SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.4,
        )
    except Exception:
        reply = None

    if not reply:
        return {
            "summary": f"基于条件 {expression} 在{market_label}完成初筛，共入选 {len(candidates)} 只标的（AI 生成失败，已回退规则文案）。",
            "dataSources": ["行情数据", "估值/财务因子", "技术指标"],
            "dimensions": ["估值", "盈利", "动量", "资金"],
            "reasons": ["筛选条件经结构化解析后执行，结果具备可解释性。"],
            "llmEnabled": False,
            "model": "rule-based",
        }

    parsed = _extract_json(reply)
    if not parsed:
        return {
            "summary": reply.strip()[:300],
            "dataSources": [],
            "dimensions": [],
            "reasons": [],
            "llmEnabled": True,
            "model": llm.LLM_MODEL,
        }
    parsed.setdefault("summary", "")
    parsed.setdefault("dataSources", [])
    parsed.setdefault("dimensions", [])
    parsed.setdefault("reasons", [])
    parsed["llmEnabled"] = True
    parsed["model"] = llm.LLM_MODEL
    return parsed


# --------------------------------------------------------------------------
# 3) 回测（复用 backtest_engine）
# --------------------------------------------------------------------------
def run_backtests(
    codes: list[str],
    strategy: str,
    start_date: str,
    end_date: str,
    pool: str = "沪深300",
    capital: int = 1_000_000,
) -> list[dict]:
    """对每只标的跑回测，返回回测结果列表。"""
    results = []
    for code in codes:
        try:
            r = be.run_backtest(strategy, start_date, end_date, pool, capital, code)
            r["code"] = code
            results.append(r)
        except Exception as exc:  # 单只失败不影响整体
            results.append({
                "code": code,
                "error": str(exc)[:200],
                "totalReturn": 0.0,
                "annualizedReturn": 0.0,
                "sharpeRatio": 0.0,
                "maxDrawdown": 0.0,
                "winRate": 0.0,
                "totalTrades": 0,
                "dataSource": "error",
            })
    return results


def _aggregate(backtests: list[dict]) -> dict:
    valid = [b for b in backtests if b.get("dataSource") != "error"]
    n = len(valid)
    if n == 0:
        return {"count": 0, "avgTotalReturn": 0.0, "avgAnnualized": 0.0,
                "avgSharpe": 0.0, "avgMaxDrawdown": 0.0, "avgWinRate": 0.0, "profitCount": 0}
    avg = lambda k: sum(b.get(k, 0.0) for b in valid) / n
    profit = sum(1 for b in valid if b.get("totalReturn", 0.0) > 0)
    return {
        "count": n,
        "avgTotalReturn": round(avg("totalReturn"), 2),
        "avgAnnualized": round(avg("annualizedReturn"), 2),
        "avgSharpe": round(avg("sharpeRatio"), 2),
        "avgMaxDrawdown": round(avg("maxDrawdown"), 2),
        "avgWinRate": round(avg("winRate"), 2),
        "profitCount": profit,
        "lossCount": n - profit,
    }


# --------------------------------------------------------------------------
# 4) 成败归因（LLM）
# --------------------------------------------------------------------------
_ATTR_SYSTEM = (
    "你是一名专业的量化研究员，服务于智能交易终端的专业用户。"
    "根据一组股票回测的汇总表现，做归因分析，必须严格只输出如下 JSON（不要任何额外文字）：\n"
    "{\n"
    '  "verdict": "success" 或 "failure",\n'
    '  "points": ["归因要点，3-5 条，客观、可解释"]\n'
    "}\n"
    "约束：若整体收益为正，verdict 取 success 并分析成功逻辑；若为负，verdict 取 failure 并分析失败原因。"
    "必须区分「市场系统性因素」与「策略/条件自身因素」，不给出确定性买卖指令，不构成投资建议。"
)


def attribute(aggregate: dict, backtests: list[dict]) -> dict:
    """返回 {verdict, points, llmEnabled}。"""
    verdict_auto = "success" if aggregate.get("avgTotalReturn", 0.0) > 0 else "failure"
    top = sorted(
        [b for b in backtests if b.get("dataSource") != "error"],
        key=lambda b: b.get("totalReturn", 0.0), reverse=True,
    )[:5]
    top_str = "、".join(f"{b.get('code')}({b.get('totalReturn',0):.1f}%)" for b in top)

    user_msg = (
        f"回测汇总（{aggregate.get('count',0)} 只有效标的）：\n"
        f"平均总收益 {aggregate.get('avgTotalReturn',0)}%，"
        f"平均年化 {aggregate.get('avgAnnualized',0)}%，"
        f"平均夏普 {aggregate.get('avgSharpe',0)}，"
        f"平均最大回撤 {aggregate.get('avgMaxDrawdown',0)}%，"
        f"平均胜率 {aggregate.get('avgWinRate',0)}%，"
        f"盈利 {aggregate.get('profitCount',0)} / 亏损 {aggregate.get('lossCount',0)}。\n"
        f"表现最好的几只：{top_str}。\n"
        "请做成败归因。"
    )

    if not llm.is_llm_enabled():
        pts = (
            [
                f"组合平均收益 {aggregate.get('avgTotalReturn',0)}%，盈利标的 {aggregate.get('profitCount',0)} 只，整体为正。",
                "成功逻辑：筛选条件在样本期内捕捉到了具备估值/盈利/动量优势的标的。",
                "建议结合分年度与分市场表现，验证条件在不同环境下的稳定性。",
            ]
            if verdict_auto == "success"
            else [
                f"组合平均收益 {aggregate.get('avgTotalReturn',0)}%，亏损标的 {aggregate.get('lossCount',0)} 只，整体为负。",
                "失败原因：可能是样本期内市场系统性下行，或所选因子在该区间失效。",
                "建议放宽/调整条件，或缩短回测区间，规避极端行情扰动。",
            ]
        )
        return {"verdict": verdict_auto, "points": pts, "llmEnabled": False, "model": "rule-based"}

    try:
        reply = llm.chat(
            [{"role": "system", "content": _ATTR_SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.4,
        )
    except Exception:
        reply = None

    if not reply:
        return {
            "verdict": verdict_auto,
            "points": ["AI 归因生成失败，已回退规则文案；请参考上方回测汇总自行判断。"],
            "llmEnabled": False,
            "model": "rule-based",
        }

    parsed = _extract_json(reply)
    if not parsed:
        return {"verdict": verdict_auto, "points": [reply.strip()[:300]], "llmEnabled": True, "model": llm.LLM_MODEL}
    parsed.setdefault("verdict", verdict_auto)
    parsed.setdefault("points", [])
    parsed["llmEnabled"] = True
    parsed["model"] = llm.LLM_MODEL
    return parsed
