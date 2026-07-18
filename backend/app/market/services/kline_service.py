"""多周期 K 线服务（需求 2）。

周期：分时(intraday) / 1分钟 / 5分钟 / 15分钟 / 30分钟 / 日K / 周K / 月K。
字段：open/high/low/close/volume/amount。历史数据来自 westock Node CLI（已验证真实源），
实时最后一棒由 QuoteService 快照更新，保证「实时 + 历史」一致。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.services.westock_client import run_table

from ..sources.base import normalize_code

logger = logging.getLogger(__name__)

# 对外周期 -> westock --period token
_PERIOD_TOKEN = {
    "1m": "min", "5m": "5min", "15m": "15min", "30m": "30min",
    "day": "day", "week": "week", "month": "month",
    "intraday": "min",  # 分时复用分钟线
}


def _pick(row: dict, *candidates: str) -> Optional[float]:
    for c in candidates:
        v = row.get(c)
        if v in (None, "", "-"):
            continue
        try:
            return float(v)
        except (ValueError, TypeError):
            continue
    return None


def _parse_kline(rows: list[dict]) -> list[dict]:
    bars = []
    for r in rows:
        dt_raw = r.get("date") or r.get("日期") or r.get("时间") or r.get("datetime") or ""
        o = _pick(r, "open", "Open", "开盘")
        h = _pick(r, "high", "High", "最高")
        l = _pick(r, "low", "Low", "最低")
        # westock K 线收盘列名为 "last"（非 "close"）
        c = _pick(r, "last", "close", "Close", "收盘")
        v = _pick(r, "volume", "Volume", "成交量")
        a = _pick(r, "amount", "Amount", "成交额")
        if c is None:
            continue
        bars.append({
            "dt": str(dt_raw),
            "open": o or c,
            "high": h or c,
            "low": l or c,
            "close": c,
            "volume": int(v or 0),
            "amount": a or 0.0,
        })
    return bars


async def get_kline(code: str, period: str = "day", limit: int = 120) -> list[dict]:
    """取某标的多周期 K 线（历史）。"""
    code6 = normalize_code(code)
    token = _PERIOD_TOKEN.get(period, "day")
    lim = max(1, min(limit, 800))
    try:
        rows = await asyncio.to_thread(
            run_table,
            ["kline", f"sh{code6}" if code6.startswith("6") else f"sz{code6}",
             "--period", token, "--limit", str(lim), "--fq", "qfq"],
            # run_table 签名：run_table(args, timeout=...)
            30,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[kline_svc] 获取 %s/%s 失败: %s", code, period, e)
        return []
    return _parse_kline(rows or [])


def closes_from_bars(bars: list[dict]) -> list[float]:
    return [b["close"] for b in bars if b.get("close") is not None]
