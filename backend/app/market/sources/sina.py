"""新浪财经实时行情源（hq.sinajs.cn）。

轻量、字段含价格/涨跌/成交量/成交额/换手（不含 PE/PB/市值）。作为故障切换「备用源 2」。
需带 Referer 头，否则返回 403。
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
_BASE = "https://hq.sinajs.cn/list="
_TIMEOUT = 8.0
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.sina.com.cn",
}


def _parse_line(sym: str, raw: str) -> Optional[Quote]:
    # 格式：var hq_str_sh600519="名称,今开,昨收,现价,最高,最低,...,成交量,成交额,...,时间,日期";
    inner = raw.split('"')[1] if '"' in raw else ""
    parts = inner.split(",")
    if len(parts) < 10:
        return None
    try:
        code6 = normalize_code(sym)
        name = parts[0]
        open_ = float(parts[1] or 0)
        prev = float(parts[2] or 0)
        price = float(parts[3] or 0)
        high = float(parts[4] or 0)
        low = float(parts[5] or 0)
        volume = int(float(parts[8] or 0))       # 手
        amount = float(parts[9] or 0)            # 元
        change = round(price - prev, 4)
        pct = round(change / prev * 100, 2) if prev else 0.0
        return Quote(
            code=code6, name=name, price=price, prev_close=prev, open=open_,
            high=high, low=low, change=change, change_pct=pct,
            volume=volume, amount=amount, source="sina",
            ts=__import__("time").time(),
        )
    except (ValueError, IndexError) as e:
        logger.warning("[sina_src] 解析失败 sym=%s: %s", sym, e)
        return None


class SinaSource(QuoteSource):
    name = "sina"
    available = True

    async def fetch_quotes(self, codes: list[str]) -> dict[str, Quote]:
        syms = [vendor_symbol(c, "sina") for c in codes]
        try:
            resp = await asyncio.to_thread(
                _SESSION.get, _BASE + ",".join(syms), headers=_HEADERS, timeout=_TIMEOUT,
            )
            resp.encoding = "gbk"
            text = resp.text or ""
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"sina request failed: {e}") from e

        out: dict[str, Quote] = {}
        for line in text.split(";"):
            line = line.strip()
            if "hq_str_" not in line:
                continue
            sym = line.split("hq_str_")[1].split("=")[0].strip()
            q = _parse_line(sym, line)
            if q:
                out[q.code] = q
        if not out:
            raise RuntimeError("sina returned empty")
        return out
