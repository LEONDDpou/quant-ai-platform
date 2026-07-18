"""市场动态 API — A 股实时盘面 + 国际新闻（v2 扩展：全市场指数 + 个股排行 + 公告资讯）"""
from fastapi import APIRouter, Query

from app.services import market_dynamics_service as mds
from app.services import international_news_service as ins

router = APIRouter()


@router.get("/a-share")
def get_a_share_dynamics():
    """获取 A 股实时动态：指数 + 热门个股 + 龙虎榜 + 板块排名 + 资金流向 + 公告资讯。"""
    return mds.get_all_dynamics()


@router.get("/a-share/hot")
def get_hot_stocks(limit: int = Query(15, ge=5, le=30)):
    """获取热门个股列表。"""
    return mds.get_hot_stocks(limit)


@router.get("/a-share/lhb")
def get_lhb(limit: int = Query(15, ge=5, le=50)):
    """获取龙虎榜（机构席位，已按code去重）。"""
    return mds.get_lhb(limit)


@router.get("/a-share/sectors")
def get_sector_rankings(limit: int = Query(31, ge=5, le=31)):
    """获取申万一级行业涨跌排名。"""
    return mds.get_sector_rankings(limit)


@router.get("/a-share/capital-flow")
def get_capital_flow():
    """获取主力资金净流向。"""
    return mds.get_capital_flow()


@router.get("/a-share/indices")
def get_market_indices():
    """获取全市场核心指数实时行情（上证/深证/创业板/科创50/沪深300等）。"""
    return mds.get_market_indices()


@router.get("/a-share/stock-rankings")
def get_stock_rankings():
    """获取个股涨跌排行（涨幅榜/成交额榜 Top 10）。"""
    return mds.get_stock_rankings()


@router.get("/a-share/news")
def get_market_news(limit: int = Query(20, ge=5, le=50)):
    """获取 A 股实时公告快讯。"""
    return mds.get_market_news(limit)


@router.get("/a-share/breadth")
def get_market_breadth():
    """获取全市场涨跌家数统计、涨停跌停数、分布区间（沪市+深市聚合）。"""
    return mds.get_market_breadth()


@router.get("/international-news")
def get_international_news(force: bool = Query(False, description="强制刷新，跳过缓存")):
    """获取国际新闻聚合（路透社/CNBC/MarketWatch + AI 中文翻译 + 真实性审核）。"""
    return ins.get_international_news(force_refresh=force)
