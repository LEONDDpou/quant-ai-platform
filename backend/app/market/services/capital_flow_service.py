"""实时资金流分析（需求 3）。

覆盖：主力资金净流入、超大单、大单、中单、小单、北向资金、龙虎榜。
底层复用已验证的 westock Node CLI（asfund / northbound / lhb）。
注：asfund 为指数级口径，对个股亦支持；大单=主力−超大单（估算），北向资金为全市场口径。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.services.market_dynamics_service import get_lhb
from app.services.westock_client import run_table

from ..sources.base import normalize_code

logger = logging.getLogger(__name__)


def _to_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


async def get_stock_capital_flow(code: str) -> dict:
    """单只个股资金流（主力/超大单/大单/中单/小单）。"""
    code6 = normalize_code(code)
    sym = f"sh{code6}" if code6.startswith("6") else f"sz{code6}"
    try:
        rows = await asyncio.to_thread(run_table, ["asfund", sym], 12)
    except Exception as e:  # noqa: BLE001
        logger.warning("[capflow] %s 资金流获取失败: %s", code, e)
        return {"code": code6, "available": False}
    if not rows:
        return {"code": code6, "available": False}
    r = rows[0]
    main = _to_float(r.get("MainNetFlow"))
    jumbo = _to_float(r.get("JumboNetFlow"))
    mid = _to_float(r.get("MidNetFlow"))
    small = _to_float(r.get("SmallNetFlow"))
    large = _to_float(r.get("LargeNetFlow"), main - jumbo if (main or jumbo) else 0.0)
    return {
        "code": code6,
        "available": True,
        "mainIn": main,
        "ultraLarge": jumbo,
        "large": large,
        "medium": mid,
        "small": small,
        "mainNetFlow5d": _to_float(r.get("MainNetFlow5D")),
    }


async def get_northbound() -> Optional[float]:
    """北向资金净流向（全市场口径，best-effort）。"""
    try:
        rows = await asyncio.to_thread(run_table, ["northbound"], 12)
    except Exception as e:  # noqa: BLE001
        logger.warning("[capflow] 北向资金获取失败: %s", e)
        return None
    if not rows:
        return None
    r = rows[0]
    for k in ("northNetFlow", "NorthNetFlow", "净买入额", "北向资金净买入", "totalNetFlow"):
        if k in r and r[k] not in (None, "", "-"):
            return _to_float(r[k])
    # 兜底：取第一个含 NetFlow 的字段
    for k, v in r.items():
        if "NetFlow" in k or "净" in str(k):
            return _to_float(v)
    return None


async def get_lhb_list(limit: int = 12) -> list[dict]:
    """龙虎榜（机构席位）。"""
    try:
        return await asyncio.to_thread(get_lhb, limit)
    except Exception as e:  # noqa: BLE001
        logger.warning("[capflow] 龙虎榜获取失败: %s", e)
        return []
