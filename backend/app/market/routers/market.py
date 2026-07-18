"""市场模块 REST API（需求 5 / 7 / 8 等）。

端点：
  GET /api/market/realtime      实时行情 + 资金流 + 技术指标 + AI 评分（AI量化接口）
  GET /api/market/quote/{code}  单只实时行情
  GET /api/market/kline         多周期 K 线
  GET /api/market/capital-flow  资金流（主力/超大单/大单/中单/小单/北向/龙虎榜）
  GET /api/market/monitor       市场监控（涨跌家数/涨跌停/排行/板块）
  GET /api/market/sources       数据源健康（故障切换状态）
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    AIScoreOut,
    BreadthOut,
    CapitalFlowOut,
    KlineBarOut,
    QuoteOut,
    RealtimeItem,
    RealtimeResponse,
    SourceHealth,
    TechOut,
)
from ..services import quote_service
from ..services.ai_score import compute_ai_score
from ..services.capital_flow_service import get_lhb_list, get_northbound, get_stock_capital_flow
from ..services.kline_service import closes_from_bars, get_kline
from ..services.market_monitor import get_breadth, get_hot, get_rankings, get_sectors
from ..services.technicals import compute_technicals
from ..sources.base import Quote, normalize_code

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Market-Realtime"])

# 轻量缓存：K线/资金流跨请求复用，避免每次实时接口打爆 westock 子进程
_KLINE_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CF_CACHE: dict[str, tuple[float, dict]] = {}
_KLINE_TTL = 60.0
_CF_TTL = 30.0


def _quote_out(q: Quote) -> QuoteOut:
    return QuoteOut(
        code=q.code, name=q.name, price=q.price, change=q.change,
        changePct=q.change_pct, volume=q.volume, amount=q.amount,
        turnover=q.turnover, pe=q.pe, pb=q.pb,
        totalMv=q.total_mv, floatMv=q.float_mv, source=q.source,
    )


async def _cached_kline(code: str) -> list[dict]:
    now = time.time()
    item = _KLINE_CACHE.get(code)
    if item and (now - item[0]) < _KLINE_TTL:
        return item[1]
    bars = await get_kline(code, "day", 60)
    _KLINE_CACHE[code] = (now, bars)
    return bars


async def _cached_cf(code: str) -> dict:
    now = time.time()
    item = _CF_CACHE.get(code)
    if item and (now - item[0]) < _CF_TTL:
        return item[1]
    cf = await get_stock_capital_flow(code)
    _CF_CACHE[code] = (now, cf)
    return cf


async def _save_ai_scores(scored: list[dict]) -> None:
    from ..services.persistence import save_ai_scores

    try:
        await save_ai_scores(scored)
    except Exception as e:  # noqa: BLE001
        logger.warning("[realtime] AI评分落库失败: %s", e)


@router.get("/realtime", response_model=RealtimeResponse)
async def realtime(codes: str = Query(..., description="逗号分隔的 A 股代码，如 600519,000858")):
    """AI 量化实时接口（需求 5）：价格/涨跌/成交量/资金流/技术指标/AI评分。"""
    code_list = [normalize_code(c) for c in codes.split(",") if normalize_code(c)]
    if not code_list:
        raise HTTPException(400, "codes 为空或格式错误")
    try:
        quotes = await quote_service.refresh(code_list)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"行情数据源不可用: {e}")

    items: list[RealtimeItem] = []
    scored: list[dict] = []
    for code, q in quotes.items():
        cf_raw = await _cached_cf(code)
        cf = None
        if cf_raw.get("available"):
            cf = CapitalFlowOut(
                code=code, mainIn=cf_raw.get("mainIn", 0.0),
                ultraLarge=cf_raw.get("ultraLarge", 0.0),
                large=cf_raw.get("large", 0.0), medium=cf_raw.get("medium", 0.0),
                small=cf_raw.get("small", 0.0), mainNetFlow5d=cf_raw.get("mainNetFlow5d", 0.0),
            )
        bars = await _cached_kline(code)
        tech = compute_technicals(closes_from_bars(bars))
        ai = compute_ai_score(q, cf_raw, tech)
        items.append(RealtimeItem(
            quote=_quote_out(q),
            capitalFlow=cf,
            technicals=TechOut(**tech),
            aiScore=AIScoreOut(**ai),
        ))
        # 异步落库 AI 评分（需求 6：AI评分落地）
        scored.append({"code": code, "name": q.name, **ai})
    # fire-and-forget 持久化
    if scored:
        asyncio.create_task(_save_ai_scores(scored))
    return RealtimeResponse(
        ts=time.strftime("%Y-%m-%d %H:%M:%S"),
        source=quote_service.orchestrator.last_source or "unknown",
        count=len(items),
        items=items,
    )


@router.get("/quote/{code}", response_model=QuoteOut)
async def quote(code: str):
    code6 = normalize_code(code)
    quotes = await quote_service.refresh([code6])
    if code6 not in quotes:
        raise HTTPException(404, f"未获取到 {code} 行情")
    return _quote_out(quotes[code6])


@router.get("/kline", response_model=list[KlineBarOut])
async def kline(
    code: str = Query(...),
    period: str = Query("day", description="1m/5m/15m/30m/day/week/month/intraday"),
    limit: int = Query(120, ge=1, le=800),
):
    bars = await get_kline(code, period, limit)
    if not bars:
        raise HTTPException(404, f"未获取到 {code} 的 {period} K线")
    # 异步落库历史 K 线（需求 6）
    asyncio.create_task(_save_klines(code, period, bars))
    return [KlineBarOut(**b) for b in bars]


async def _save_klines(code: str, period: str, bars: list[dict]) -> None:
    from ..services.persistence import save_klines

    try:
        await save_klines(code, period, bars)
    except Exception as e:  # noqa: BLE001
        logger.warning("[kline] K线落库失败: %s", e)


@router.get("/capital-flow")
async def capital_flow(codes: str = Query("", description="逗号分隔代码；为空则返回北向+龙虎榜")):
    code_list = [normalize_code(c) for c in codes.split(",") if normalize_code(c)]
    tasks = [get_stock_capital_flow(c) for c in code_list]
    results = await asyncio.gather(*tasks)
    out = [CapitalFlowOut(
        code=r["code"], available=r.get("available", False),
        mainIn=r.get("mainIn", 0.0), ultraLarge=r.get("ultraLarge", 0.0),
        large=r.get("large", 0.0), medium=r.get("medium", 0.0),
        small=r.get("small", 0.0), mainNetFlow5d=r.get("mainNetFlow5d", 0.0),
    ) for r in results]
    north = await get_northbound()
    lhb = await get_lhb_list(12)
    return {"items": out, "northbound": north, "lhb": lhb}


@router.get("/monitor")
async def monitor():
    breadth, rankings, hot, sectors = await asyncio.gather(
        get_breadth(), get_rankings(), get_hot(15), get_sectors(31),
    )
    agg = (breadth or {}).get("aggregate") or {}
    return {
        "breadth": BreadthOut(
            total=agg.get("total", 0), upCount=agg.get("upCount", 0),
            downCount=agg.get("downCount", 0), flatCount=agg.get("flatCount", 0),
            limitUp=agg.get("limitUp", 0), limitDown=agg.get("limitDown", 0),
            breadthPct=agg.get("breadthPct", 0.0),
        ),
        "rankings": rankings,
        "hotStocks": hot,
        "sectorRankings": sectors,
    }


@router.get("/sources", response_model=list[SourceHealth])
async def sources():
    return [SourceHealth(**h) for h in quote_service.source_health()]
