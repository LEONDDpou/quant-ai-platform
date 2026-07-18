"""策略市场路由（#183）。

端点（前缀 /api/paper/strategy-marketplace）：
- POST  /publish            ：发布策略
- POST  /{id}/unpublish     ：下架策略（仅作者）
- GET   /listing            ：市场浏览列表
- GET   /search             ：按标签搜索
- GET   /my-published       ：我发布的策略
- GET   /my-subscriptions   ：我的订阅（含发布信息）
- GET   /leaderboard        ：排行榜
- POST  /subscribe          ：订阅策略
- POST  /unsubscribe        ：取消订阅
- POST  /rate               ：评分/评价
- GET   /{id}               ：策略详情
- GET   /{id}/ratings       ：某策略的评分列表

注意：静态路径（listing / search / my-published / my-subscriptions / leaderboard）必须
定义在动态路径 {id} 之前，否则 FastAPI 会将静态路径文本作为 int 参数解析导致 422。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.paper.errors import PaperError
from app.paper.schemas import (
    MarketplaceLeaderboardEntry,
    PublishedStrategyResponse,
    PublishStrategyRequest,
    StrategyMarketplaceListing,
    StrategyRatingRequest,
    StrategyRatingResponse,
    SubscribeRequest,
)
from app.paper.services.strategy_marketplace_service import StrategyMarketplaceService

router = APIRouter(tags=["PaperMarketplace"])
_mkt = StrategyMarketplaceService()


# ———— 静态路径（在动态 {id} 之前） ————

@router.post("/publish", response_model=PublishedStrategyResponse)
def publish_strategy(req: PublishStrategyRequest):
    try:
        return _mkt.publish(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{strategy_id}/unpublish")
def unpublish_strategy(strategy_id: int, account_id: int = Query(...)):
    try:
        ok = _mkt.unpublish(strategy_id, account_id)
        return {"unpublished": ok}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/listing", response_model=list[StrategyMarketplaceListing])
def list_marketplace(limit: int = Query(50), offset: int = Query(0)):
    return _mkt.list_marketplace(limit, offset)


@router.get("/search", response_model=list[StrategyMarketplaceListing])
def search_marketplace(tag: str = Query(...), limit: int = Query(20)):
    return _mkt.search_by_tag(tag, limit)


@router.get("/my-published", response_model=list[PublishedStrategyResponse])
def my_published_strategies(account_id: int = Query(...)):
    return _mkt.list_my_published(account_id)


@router.get("/my-subscriptions")
def my_subscriptions(account_id: int = Query(...)):
    return _mkt.list_my_subscriptions(account_id)


@router.get("/leaderboard", response_model=list[MarketplaceLeaderboardEntry])
def leaderboard(limit: int = Query(20)):
    return _mkt.get_leaderboard(limit)


@router.post("/subscribe")
def subscribe_strategy(req: SubscribeRequest):
    try:
        return _mkt.subscribe(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/unsubscribe")
def unsubscribe_strategy(account_id: int = Query(...), published_strategy_id: int = Query(...)):
    try:
        ok = _mkt.unsubscribe(account_id, published_strategy_id)
        return {"unsubscribed": ok}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rate", response_model=StrategyRatingResponse)
def rate_strategy(req: StrategyRatingRequest):
    try:
        return _mkt.rate(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ———— 动态路径（含 {id} 参数） ————

@router.get("/{strategy_id}", response_model=PublishedStrategyResponse)
def get_published_strategy(strategy_id: int):
    obj = _mkt.get_published_detail(strategy_id)
    if not obj:
        raise HTTPException(status_code=404, detail="策略不存在")
    return obj


@router.get("/{strategy_id}/ratings", response_model=list[StrategyRatingResponse])
def list_ratings(strategy_id: int):
    return _mkt.list_ratings(strategy_id)
