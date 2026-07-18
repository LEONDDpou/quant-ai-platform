"""腾讯自选股实时行情源（qt.gtimg.cn，HTTP 直连、绕过坏代理）。

复用平台既有 tencent_quote 的字段解析（索引已验证），并扩展 PE/PB/总市值/流通市值。
作为故障切换的「主用源」——在本环境实测稳定可用。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import requests

from .base import Quote, QuoteSource, normalize_code, vendor_symbol

logger = logging.getLogger(__name__)

# 直连 HTTP + 忽略环境代理（沙箱经代理的 HTTPS 握手失败、HTTP 被 502）
_SESSION = requests.Session()
_SESSION.trust_env = False
_TENCENT_URL = "http://qt.gtimg.cn/q="
_TIMEOUT = 8.0


def _parse_row(sym: str, raw: str) -> Optional[Quote]:
    """解析腾讯 ``~`` 分隔串（字段索引见既有实现，已验证）。"""
    parts = raw.split("~")
    if len(parts) < 35:
        return None
    try:
        code6 = sym[-6:]
        prev = float(parts[4])
        price = float(parts[3])
        high = float(parts[33])
        low = float(parts[34])
        change = float(parts[31])
        change_pct = float(parts[32])
        turnover = float(parts[38]) if len(parts) > 38 and parts[38] not in ("", "-") else 0.0
        amount = float(parts[37]) if len(parts) > 37 and parts[37] not in ("", "-") else 0.0
        # 扩展字段（best-effort，腾讯部分变体才返回）
        pe = float(parts[39]) if len(parts) > 39 and parts[39] not in ("", "-") else 0.0
        pb = float(parts[40]) if len(parts) > 40 and parts[40] not in ("", "-") else 0.0
        # 44=总市值(亿) 45=流通市值(亿)
        total_mv = (float(parts[44]) * 1e8) if len(parts) > 44 and parts[44] not in ("", "-") else 0.0
        float_mv = (float(parts[45]) * 1e8) if len(parts) > 45 and parts[45] not in ("", "-") else 0.0

        def _f(i: int) -> float:
            try:
                return float(parts[i])
            except (ValueError, IndexError):
                return 0.0

        return Quote(
            code=code6,
            name=parts[1],
            price=price,
            prev_close=prev,
            open=_f(5),
            high=high,
            low=low,
            change=change,
            change_pct=change_pct,
            volume=int(_f(6)),
            amount=amount,
            turnover=turnover,
            pe=pe,
            pb=pb,
            total_mv=total_mv,
            float_mv=float_mv,
            source="tencent",
            ts=time.time(),
        )
    except (ValueError, IndexError) as e:
        logger.warning("[tencent_src] 解析失败 sym=%s: %s", sym, e)
        return None


class TencentSource(QuoteSource):
    name = "tencent"
    available = True

    async def fetch_quotes(self, codes: list[str]) -> dict[str, Quote]:
        syms = [vendor_symbol(c, "tencent") for c in codes]
        url = _TENCENT_URL + ",".join(syms)
        try:
            resp = await asyncio.to_thread(
                _SESSION.get,
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "https://gu.qq.com/",
                },
                timeout=_TIMEOUT,
            )
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"tencent request failed: {e}") from e

        resp.encoding = "gbk"
        text = resp.text or ""
        out: dict[str, Quote] = {}
        for line in text.split(";"):
            line = line.strip()
            if not line.startswith("v_"):
                continue
            key, _, val = line.partition("=")
            sym = key[2:].lower()
            raw = val.strip().strip('"').strip("'")
            if not raw:
                continue
            q = _parse_row(sym, raw)
            if q:
                out[q.code] = q
        if not out:
            raise RuntimeError("tencent returned empty")
        return out
