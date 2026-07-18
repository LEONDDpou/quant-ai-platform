"""技术指标计算（需求 5：AI量化接口返回技术指标）。

纯函数、基于历史收盘价序列，使用 pandas/numpy。覆盖 MA、RSI、MACD。
作为 AI 评分与策略接口的底层因子，计算透明、可复现。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def compute_technicals(closes: list[float], highs: Optional[list[float]] = None,
                       lows: Optional[list[float]] = None) -> dict:
    """返回 {ma5, ma10, ma20, rsi14, macd, macd_signal, macd_hist}。"""
    out = {
        "ma5": None, "ma10": None, "ma20": None,
        "rsi14": None, "macd": None, "macdSignal": None, "macdHist": None,
    }
    if not closes or len(closes) < 2:
        return out

    s = pd.Series(closes, dtype="float64")
    if len(s) >= 5:
        out["ma5"] = round(float(s.rolling(5).mean().iloc[-1]), 3)
    if len(s) >= 10:
        out["ma10"] = round(float(s.rolling(10).mean().iloc[-1]), 3)
    if len(s) >= 20:
        out["ma20"] = round(float(s.rolling(20).mean().iloc[-1]), 3)

    # RSI(14)
    if len(s) >= 15:
        delta = s.diff().dropna()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.rolling(14).mean().iloc[-1]
        avg_loss = loss.rolling(14).mean().iloc[-1]
        if avg_loss and avg_loss > 0:
            rs = avg_gain / avg_loss
            out["rsi14"] = round(float(100 - 100 / (1 + rs)), 2)
        elif avg_gain and avg_gain > 0:
            out["rsi14"] = 100.0
        else:
            out["rsi14"] = 50.0

    # MACD(12,26,9)
    if len(s) >= 27:
        ema12 = s.ewm(span=12, adjust=False).mean()
        ema26 = s.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        hist = (dif - dea) * 2
        out["macd"] = round(float(dif.iloc[-1]), 3)
        out["macdSignal"] = round(float(dea.iloc[-1]), 3)
        out["macdHist"] = round(float(hist.iloc[-1]), 3)

    return out


def momentum_score(change_pct: float) -> float:
    """动量因子：将日涨跌幅映射到 [-1,1]（±10% 视为满格）。"""
    return float(np.clip(change_pct / 10.0, -1.0, 1.0))
