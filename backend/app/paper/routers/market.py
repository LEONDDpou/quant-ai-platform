"""模拟盘交易系统 — 行情接口（M2）。

挂载前缀（在 main.py 中 include_router）：/api/paper/market
提供：实时行情 / 五档盘口 / K线（含分钟级）/ 资金流向 / 行业·概念板块 / 主要指数 / 数据源状态。
所有接口均通过 MarketProvider 获取，真实源不可用时自动回退模拟数据。
"""
from fastapi import APIRouter, HTTPException, Query

from app.paper.services.market_provider import market_provider
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperMarket"])


@router.get("/quote/{code}")
def get_quote(code: str):
    """实时行情（盘口级快照：最新价/昨收/开/高/低/量/额/换手率/振幅/涨跌幅）。"""
    try:
        return market_provider.quote(code)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/orderbook/{code}")
def get_order_book(code: str):
    """五档行情（买一~买五、卖一~卖五）。"""
    try:
        return market_provider.order_book(code)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/kline/{code}")
def get_kline(
    code: str,
    period: str = Query("day", description="1m/5m/15m/30m/60m/day/week/month"),
    limit: int = Query(120, description="返回根数（10-500）", ge=10, le=500),
):
    """K 线序列（支持分钟级与日/周/月）。"""
    try:
        return market_provider.kline(code, period, limit)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/capital-flow/{code}")
def get_capital_flow(code: str):
    """资金流向（主力/超大单/大单/中单/小单净流入）。"""
    try:
        return market_provider.capital_flow(code)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/sectors")
def get_sectors(kind: str = Query("industry", description="industry / concept")):
    """行业 / 概念板块列表（含涨跌幅与领涨股）。"""
    try:
        return market_provider.sectors(kind)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/indices")
def get_indices():
    """主要指数实时行情（复用平台 data_provider）。"""
    return market_provider.indices()


@router.get("/status")
def get_status():
    """数据源状态（akshare 是否可用 / 当前模式 / 缓存条目数）。"""
    return market_provider.status()
