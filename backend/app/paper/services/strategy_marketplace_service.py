"""策略市场服务层（#183）。

能力：发布策略（从回测/想法/手动）、上下架、市场浏览/搜索、
      订阅（创建本地副本）、评分/评价、排行榜。
"""
import json
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from app.paper.domain_models import (
    BacktestRun,
    PaperPublishedStrategy,
    PaperStrategy,
    PaperStrategyIdea,
    PaperStrategyRating,
    PaperStrategySubscription,
)
from app.paper.errors import PaperError
from app.paper.repositories.marketplace_repo import (
    PublishedStrategyRepository,
    RatingRepository,
    SubscriptionRepository,
)
from app.paper.repositories.base import BaseRepository
from app.paper.schemas import (
    MarketplaceLeaderboardEntry,
    PublishedStrategyResponse,
    PublishStrategyRequest,
    StrategyMarketplaceListing,
    StrategyRatingRequest,
    StrategyRatingResponse,
    SubscribeRequest,
)


class StrategyMarketplaceService:
    """策略市场编排服务。"""

    def __init__(self):
        self.pub_repo = PublishedStrategyRepository()
        self.sub_repo = SubscriptionRepository()
        self.rating_repo = RatingRepository()

    # ====================== 发布 ======================

    def publish(self, req: PublishStrategyRequest) -> PublishedStrategyResponse:
        """发布策略到市场。"""
        source_type = req.sourceType
        source_id = req.sourceId
        entry_rules = req.entryRules or []
        exit_rules = req.exitRules or []
        risk = req.risk or {}
        universe = req.universe or []
        perf = req.performanceSnapshot or {}

        # 如果有 sourceId，尝试从源拉取数据补齐
        if source_id and source_type == "backtest":
            bt = self._get_backtest(source_id)
            if bt:
                if not entry_rules and bt.params:
                    entry_rules = bt.params.get("rules", [])
                if not universe and bt.symbol:
                    universe = [bt.symbol]
                perf = perf or {
                    "totalReturn": bt.total_return,
                    "sharpeRatio": bt.sharpe_ratio,
                    "maxDrawdown": bt.max_drawdown,
                    "winRate": bt.win_rate,
                    "totalTrades": bt.total_trades,
                }
        elif source_id and source_type == "idea":
            idea = self._get_idea(source_id)
            if idea:
                if not entry_rules:
                    entry_rules = idea.entry_rules or []
                if not exit_rules:
                    exit_rules = idea.exit_rules or []
                if not risk:
                    risk = idea.risk or {}
                if not universe:
                    universe = idea.universe or []

        obj = PaperPublishedStrategy(
            author_account_id=req.accountId,
            name=req.name,
            description=req.description,
            source_type=source_type,
            source_id=source_id,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            risk=risk,
            universe=universe,
            logic=req.logic,
            performance_snapshot=perf,
            tags=req.tags,
            version=1,
            is_published=True,
        )
        self.pub_repo.add(obj)
        return self._ps_to_resp(obj)

    def unpublish(self, strategy_id: int, account_id: int) -> bool:
        """下架策略（仅作者可操作）。"""
        obj = self.pub_repo.get_published(strategy_id)
        if not obj:
            raise PaperError("策略不存在")
        if obj.author_account_id != account_id:
            raise PaperError("仅发布者可下架")
        return self.pub_repo.set_publish_status(strategy_id, False)

    # ====================== 市场浏览 ======================

    def list_marketplace(self, limit: int = 50, offset: int = 0) -> List[StrategyMarketplaceListing]:
        """列出市场上架策略（含聚合指标）。"""
        objs = self.pub_repo.list_published(limit, offset)
        return [self._to_listing(o) for o in objs]

    def search_by_tag(self, tag: str, limit: int = 20) -> List[StrategyMarketplaceListing]:
        """按标签搜索。"""
        objs = self.pub_repo.search_by_tag(tag, limit)
        return [self._to_listing(o) for o in objs]

    def get_published_detail(self, strategy_id: int) -> Optional[PublishedStrategyResponse]:
        """获取发布策略详情。"""
        obj = self.pub_repo.get_published(strategy_id)
        if not obj:
            return None
        return self._ps_to_resp(obj)

    def list_my_published(self, account_id: int) -> List[PublishedStrategyResponse]:
        """列出我发布的策略。"""
        objs = self.pub_repo.list_by_author(account_id)
        return [self._ps_to_resp(o) for o in objs]

    # ====================== 订阅 ======================

    def subscribe(self, req: SubscribeRequest) -> dict:
        """订阅策略（创建本地 PaperStrategy 副本）。"""
        pub = self.pub_repo.get_published(req.publishedStrategyId)
        if not pub or not pub.is_published:
            raise PaperError("策略不存在或已下架")
        existing = self.sub_repo.find_active(req.accountId, req.publishedStrategyId)
        if existing:
            return {"subId": existing.id, "localStrategyId": existing.local_strategy_id, "alreadySubscribed": True}

        # 创建本地策略副本
        local_id = str(uuid4())
        local = PaperStrategy(
            id=local_id,
            account_id=req.accountId,
            name=pub.name,
            description=pub.description,
            enabled=False,
            params={
                "entry_rules": pub.entry_rules or [],
                "exit_rules": pub.exit_rules or [],
                "risk": pub.risk or {},
                "universe": pub.universe or [],
                "marketplaceId": pub.id,
            },
        )
        sub = PaperStrategySubscription(
            account_id=req.accountId,
            published_strategy_id=req.publishedStrategyId,
            local_strategy_id=local_id,
            is_active=True,
        )
        base = BaseRepository()
        base.model = PaperStrategy
        base.add(local)
        self.sub_repo.add(sub)
        return {"subId": sub.id, "localStrategyId": local_id, "alreadySubscribed": False}

    def unsubscribe(self, account_id: int, published_strategy_id: int) -> bool:
        """取消订阅。"""
        sub = self.sub_repo.find_active(account_id, published_strategy_id)
        if not sub:
            raise PaperError("未订阅该策略")
        return self.sub_repo.unsubscribe(sub.id)

    def list_my_subscriptions(self, account_id: int) -> list:
        """列出我的订阅（含发布策略信息）。"""
        subs = self.sub_repo.list_by_account(account_id)
        result = []
        for s in subs:
            pub = self.pub_repo.get_published(s.published_strategy_id)
            result.append({
                "subId": s.id,
                "publishedStrategyId": s.published_strategy_id,
                "localStrategyId": s.local_strategy_id,
                "subscribedAt": s.subscribed_at.isoformat() if s.subscribed_at else "",
                "publishedStrategy": self._ps_to_resp(pub) if pub else None,
            })
        return result

    # ====================== 评分 ======================

    def rate(self, req: StrategyRatingRequest) -> StrategyRatingResponse:
        """评分/评价策略（已有评分则更新）。"""
        if req.score < 1 or req.score > 5:
            raise PaperError("评分必须在 1-5 之间")
        existing = self.rating_repo.find_by_user(req.accountId, req.publishedStrategyId)
        if existing:
            existing.score = req.score
            existing.review = req.review
            with self.rating_repo._session() as db:
                db.commit()
            return self._rating_to_resp(existing)
        rating = PaperStrategyRating(
            account_id=req.accountId,
            published_strategy_id=req.publishedStrategyId,
            score=req.score,
            review=req.review,
        )
        self.rating_repo.add(rating)
        return self._rating_to_resp(rating)

    def list_ratings(self, published_strategy_id: int) -> List[StrategyRatingResponse]:
        """列出某策略的所有评分。"""
        ratings = self.rating_repo.list_by_strategy(published_strategy_id)
        return [self._rating_to_resp(r) for r in ratings]

    # ====================== 排行榜 ======================

    def get_leaderboard(self, limit: int = 20) -> List[MarketplaceLeaderboardEntry]:
        """综合排行榜：按平均评分 + 订阅数排序。"""
        objs = self.pub_repo.list_published(limit=100)
        entries = []
        for o in objs:
            avg_r = self.rating_repo.avg_score(o.id)
            r_cnt = self.rating_repo.count_by_strategy(o.id)
            s_cnt = self.sub_repo.count_by_strategy(o.id)
            # 综合分 = 平均评分权重 0.6 + 订阅数归一化权重 0.4
            composite = round(avg_r * 0.6 + min(s_cnt / 10.0, 5.0) * 0.4, 2)
            entries.append(MarketplaceLeaderboardEntry(
                publishedStrategyId=o.id,
                name=o.name,
                authorAccountId=o.author_account_id,
                avgRating=avg_r,
                ratingCount=r_cnt,
                subscriberCount=s_cnt,
                compositeScore=composite,
            ))
        entries.sort(key=lambda x: x.compositeScore, reverse=True)
        return entries[:limit]

    # ====================== 内部辅助 ======================

    def _get_backtest(self, run_id: int) -> Optional[BacktestRun]:
        bt_repo = BaseRepository()
        bt_repo.model = BacktestRun
        return bt_repo.get(run_id)

    def _get_idea(self, idea_id: int) -> Optional[PaperStrategyIdea]:
        idea_repo = BaseRepository()
        idea_repo.model = PaperStrategyIdea
        return idea_repo.get(idea_id)

    def _ps_to_resp(self, obj: PaperPublishedStrategy) -> PublishedStrategyResponse:
        return PublishedStrategyResponse(
            id=obj.id,
            authorAccountId=obj.author_account_id,
            name=obj.name,
            description=obj.description or "",
            sourceType=obj.source_type or "manual",
            sourceId=obj.source_id,
            entryRules=obj.entry_rules or [],
            exitRules=obj.exit_rules or [],
            risk=obj.risk or {},
            universe=obj.universe or [],
            logic=obj.logic or "",
            performanceSnapshot=obj.performance_snapshot or {},
            tags=obj.tags or [],
            version=obj.version or 1,
            isPublished=obj.is_published if obj.is_published is not None else True,
            createdAt=obj.created_at.isoformat() if obj.created_at else "",
            updatedAt=obj.updated_at.isoformat() if obj.updated_at else "",
        )

    def _to_listing(self, obj: PaperPublishedStrategy) -> StrategyMarketplaceListing:
        avg_r = self.rating_repo.avg_score(obj.id)
        r_cnt = self.rating_repo.count_by_strategy(obj.id)
        s_cnt = self.sub_repo.count_by_strategy(obj.id)
        return StrategyMarketplaceListing(
            id=obj.id,
            authorAccountId=obj.author_account_id,
            name=obj.name,
            description=obj.description or "",
            sourceType=obj.source_type or "manual",
            tags=obj.tags or [],
            isPublished=obj.is_published if obj.is_published is not None else True,
            avgRating=avg_r,
            ratingCount=r_cnt,
            subscriberCount=s_cnt,
            performanceSnapshot=obj.performance_snapshot or {},
            createdAt=obj.created_at.isoformat() if obj.created_at else "",
        )

    def _rating_to_resp(self, r: PaperStrategyRating) -> StrategyRatingResponse:
        return StrategyRatingResponse(
            id=r.id,
            accountId=r.account_id,
            publishedStrategyId=r.published_strategy_id,
            score=r.score,
            review=r.review or "",
            createdAt=r.created_at.isoformat() if r.created_at else "",
        )
