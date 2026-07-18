"""AI 选股评分（需求 5 / 需求 9：AI评分）。

透明、可复现的启发式评分（**非投资建议、非交易信号**）：
  综合得分 = 50 + 动量×20 + 资金面×15 + 技术面(RSI 偏离)×15 + 趋势(MA) ×10
  全部因子可解释，便于审计与调参。评分为模型驱动结果，仅供研究参考。
"""
from __future__ import annotations

from typing import Optional

from ..sources.base import Quote
from .technicals import momentum_score


def compute_ai_score(
    quote: Quote,
    capital: Optional[dict] = None,
    tech: Optional[dict] = None,
    volatility: float = 0.0,
) -> dict:
    tech = tech or {}
    capital = capital or {}

    momentum = momentum_score(quote.change_pct)            # [-1,1]
    rsi = tech.get("rsi14")
    rsi_component = ((rsi - 50) / 50.0) if rsi is not None else 0.0   # [-1,1]

    # 资金面：主力净流入占流通市值比例（对抗不同市值尺度），做 tanh 压缩
    import math

    float_mv = max(quote.float_mv, 1.0)
    main_in = float(capital.get("main_in") or capital.get("mainNetFlow") or 0.0)
    fund_ratio = main_in / float_mv
    fund_component = math.tanh(fund_ratio * 50.0)          # [-1,1]

    # 趋势：价格高于 MA20 为正
    ma20 = tech.get("ma20")
    trend_component = 0.0
    if ma20 and quote.price and ma20 > 0:
        trend_component = max(-1.0, min(1.0, (quote.price - ma20) / ma20 * 10.0))

    score = 50 + momentum * 20 + fund_component * 15 + rsi_component * 15 + trend_component * 10
    score = max(0.0, min(100.0, round(score, 1)))

    # 风险等级
    if (rsi is not None and (rsi > 80 or rsi < 20)) or abs(quote.change_pct) >= 9.5:
        risk_level = "high"
    elif (rsi is not None and (rsi > 70 or rsi < 30)) or abs(quote.change_pct) >= 5:
        risk_level = "mid"
    else:
        risk_level = "low"

    return {
        "score": score,
        "techScore": round(50 + rsi_component * 25 + trend_component * 25, 1),
        "fundScore": round(50 + fund_component * 50, 1),
        "sentimentScore": round(50 + momentum * 50, 1),
        "momentum": round(momentum, 3),
        "volatility": round(volatility, 4),
        "riskLevel": risk_level,
    }
