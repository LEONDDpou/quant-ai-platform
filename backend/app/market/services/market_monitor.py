"""市场监控（需求 4）。

实时计算：涨停/跌停数量、上涨/下跌数量、成交额排名、资金流排名、行业涨幅排名。
复用既有 market_dynamics_service 的已验证函数（changedist / hot / sector / rankings），
以线程方式调用（其内部为同步 subprocess shell-out）。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.services.market_dynamics_service import (
    get_hot_stocks,
    get_market_breadth,
    get_sector_rankings,
    get_stock_rankings,
)

logger = logging.getLogger(__name__)


async def get_breadth() -> dict:
    """涨跌家数 / 涨跌停统计。"""
    try:
        return await asyncio.to_thread(get_market_breadth)
    except Exception as e:  # noqa: BLE001
        logger.warning("[monitor] 市场宽度获取失败: %s", e)
        return {"aggregate": {"total": 0, "upCount": 0, "downCount": 0,
                              "flatCount": 0, "limitUp": 0, "limitDown": 0, "breadthPct": 0}}


async def get_rankings() -> dict:
    """涨幅榜 / 跌幅榜。"""
    try:
        return await asyncio.to_thread(get_stock_rankings)
    except Exception as e:  # noqa: BLE001
        logger.warning("[monitor] 排行获取失败: %s", e)
        return {"topGainers": [], "topLosers": []}


async def get_hot(limit: int = 15) -> list[dict]:
    try:
        return await asyncio.to_thread(get_hot_stocks, limit)
    except Exception as e:  # noqa: BLE001
        logger.warning("[monitor] 热门获取失败: %s", e)
        return []


async def get_sectors(limit: int = 31) -> list[dict]:
    try:
        return await asyncio.to_thread(get_sector_rankings, limit)
    except Exception as e:  # noqa: BLE001
        logger.warning("[monitor] 板块排名获取失败: %s", e)
        return []
