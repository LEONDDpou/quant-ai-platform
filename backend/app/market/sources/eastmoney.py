"""东方财富实时行情源（push2.eastmoney.com）。

字段全（含 PE/PB/总市值/流通市值）。作为故障切换的「备用源 1」。
注意：本沙箱若经代理出网可能被拦截，拦截时抛异常由编排器切换到下一源。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import requests

from .base import Quote, QuoteSource, normalize_code, vendor_symbol

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.trust_env = False
_BASE = "https://push2.eastmoney.com/api/qt/ulist.np/get"
_FIELDS = "f1,f2,f3,f4,f5,f6,f8,f9,f10,f12,f13,f14,f20,f21"
_TIMEOUT = 8.0

# f 字段 -> 含义
# f2 最新价 f3 涨跌幅 f4 涨跌额 f5 成交量(手) f6 成交额 f8 换手率
# f9 市盈率 f10 市净率 f12 代码 f13 市场 f14 名称 f20 总市值 f21 流通市值


def _parse_diff(item: dict) -> Optional[Quote]:
    code = str(item.get("f12", "")).strip()
    if not code or len(code) != 6:
        return None
    try:
        price = float(item.get("f2") or 0)
        prev = float(item.get("f4") or 0)
        pct = float(item.get("f3") or 0)
        # 东财 f4 为涨跌额；若缺，用 price - (price/(1+pct/100)) 估算
        change = prev
        if not change:
            change = round(price - price / (1 + pct / 100.0), 4) if pct else 0.0
        return Quote(
            code=code,
            name=str(item.get("f14", "")),
            price=price,
            change=change,
            change_pct=pct,
            volume=int(float(item.get("f5") or 0)),
            amount=float(item.get("f6") or 0),
            turnover=float(item.get("f8") or 0),
            pe=float(item.get("f9") or 0),
            pb=float(item.get("f10") or 0),
            total_mv=float(item.get("f20") or 0),
            float_mv=float(item.get("f21") or 0),
            source="eastmoney",
            ts=__import__("time").time(),
        )
    except (ValueError, TypeError) as e:
        logger.warning("[eastmoney_src] 解析失败: %s", e)
        return None


class EastMoneySource(QuoteSource):
    name = "eastmoney"
    available = True

    async def fetch_quotes(self, codes: list[str]) -> dict[str, Quote]:
        secids = [vendor_symbol(c, "eastmoney") for c in codes]
        params = {
            "fltt": "2",
            "invt": "2",
            "fields": _FIELDS,
            "secids": ",".join(secids),
        }
        try:
            resp = await asyncio.to_thread(
                _SESSION.get, _BASE, params=params, timeout=_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"eastmoney request failed: {e}") from e

        diff = (data.get("data") or {}).get("diff") or []
        out: dict[str, Quote] = {}
        for item in diff:
            q = _parse_diff(item)
            if q:
                out[q.code] = q
        if not out:
            raise RuntimeError("eastmoney returned empty")
        return out
