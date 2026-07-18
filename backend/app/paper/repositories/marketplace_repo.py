"""策略市场仓储层（#183）。

三个 Repository：PublishedStrategyRepository / SubscriptionRepository / RatingRepository。
"""
from typing import List, Optional

from sqlalchemy import desc, func

from app.paper.domain_models import (
    PaperPublishedStrategy,
    PaperStrategyRating,
    PaperStrategySubscription,
)
from app.paper.errors import PaperError
from app.paper.repositories.base import BaseRepository


class PublishedStrategyRepository(BaseRepository):
    """已发布策略的仓储。"""

    model = PaperPublishedStrategy

    def list_published(self, limit: int = 50, offset: int = 0) -> List[PaperPublishedStrategy]:
        """列出所有上架的策略。"""
        with self._session() as db:
            return (
                db.query(self.model)
                .filter(self.model.is_published == True)  # noqa: E712
                .order_by(desc(self.model.updated_at))
                .offset(offset)
                .limit(limit)
                .all()
            )

    def search_by_tag(self, tag: str, limit: int = 20) -> List[PaperPublishedStrategy]:
        """按标签模糊搜索已发布策略。

        取全部已发布策略后在 Python 侧过滤（数量通常 <200），免去跨 DB JSON 查询兼容问题。
        """
        all_published = self.list_published(limit=200)
        tag_lower = tag.lower()
        matched = [
            s for s in all_published
            if any(tag_lower in (t or "").lower() for t in (s.tags or []))
        ]
        return matched[:limit]

    def list_by_author(self, author_id: int) -> List[PaperPublishedStrategy]:
        """按发布者列出策略。"""
        with self._session() as db:
            return (
                db.query(self.model)
                .filter(self.model.author_account_id == author_id)
                .order_by(desc(self.model.updated_at))
                .all()
            )

    def get_published(self, strategy_id: int) -> Optional[PaperPublishedStrategy]:
        """按 ID 获取（不限发布状态）。"""
        return self.get(strategy_id)

    def set_publish_status(self, strategy_id: int, is_published: bool) -> bool:
        """上架/下架。"""
        with self._session() as db:
            obj = db.query(self.model).filter_by(id=strategy_id).first()
            if not obj:
                return False
            obj.is_published = is_published
            db.commit()
            return True


class SubscriptionRepository(BaseRepository):
    """订阅仓储。"""

    model = PaperStrategySubscription

    def list_by_account(self, account_id: int) -> List[PaperStrategySubscription]:
        """列出某账户的活跃订阅。"""
        with self._session() as db:
            return (
                db.query(self.model)
                .filter(
                    self.model.account_id == account_id,
                    self.model.is_active == True,  # noqa: E712
                )
                .all()
            )

    def count_by_strategy(self, published_strategy_id: int) -> int:
        """统计某策略的活跃订阅数。"""
        with self._session() as db:
            return db.query(self.model).filter(
                self.model.published_strategy_id == published_strategy_id,
                self.model.is_active == True,  # noqa: E712
            ).count()

    def find_active(self, account_id: int, published_strategy_id: int) -> Optional[PaperStrategySubscription]:
        """查找某账户对某策略的活跃订阅。"""
        with self._session() as db:
            return db.query(self.model).filter(
                self.model.account_id == account_id,
                self.model.published_strategy_id == published_strategy_id,
                self.model.is_active == True,  # noqa: E712
            ).first()

    def unsubscribe(self, sub_id: int) -> bool:
        """取消订阅（软删除）。"""
        with self._session() as db:
            obj = db.query(self.model).filter_by(id=sub_id).first()
            if not obj:
                return False
            obj.is_active = False
            from datetime import datetime
            obj.unsubscribed_at = datetime.utcnow()
            db.commit()
            return True


class RatingRepository(BaseRepository):
    """评分仓储。"""

    model = PaperStrategyRating

    def list_by_strategy(self, published_strategy_id: int) -> List[PaperStrategyRating]:
        """列出某策略的所有评分。"""
        with self._session() as db:
            return (
                db.query(self.model)
                .filter(self.model.published_strategy_id == published_strategy_id)
                .order_by(desc(self.model.created_at))
                .all()
            )

    def find_by_user(self, account_id: int, published_strategy_id: int) -> Optional[PaperStrategyRating]:
        """查找某用户对某策略的已有评分。"""
        with self._session() as db:
            return db.query(self.model).filter(
                self.model.account_id == account_id,
                self.model.published_strategy_id == published_strategy_id,
            ).first()

    def avg_score(self, published_strategy_id: int) -> float:
        """计算某策略的平均评分。"""
        with self._session() as db:
            result = db.query(func.avg(self.model.score)).filter(
                self.model.published_strategy_id == published_strategy_id,
            ).scalar()
            return round(float(result), 2) if result else 0.0

    def count_by_strategy(self, published_strategy_id: int) -> int:
        """统计某策略的评分人数。"""
        with self._session() as db:
            return db.query(self.model).filter(
                self.model.published_strategy_id == published_strategy_id,
            ).count()
