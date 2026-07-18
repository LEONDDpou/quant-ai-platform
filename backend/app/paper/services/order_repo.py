"""模拟盘交易系统 — 订单仓储。

订单的「撮合变更」在 order_service 的事务内完成；本仓储负责列表 / 详情 / 状态检索
等读写，以及撤单的轻量状态翻转。
"""
from typing import List, Optional

from app.paper.domain_models import PaperOrder
from app.paper.repositories.base import BaseRepository


class OrderRepository(BaseRepository):
    """订单持久化。"""

    model = PaperOrder

    def list_orders(self, account_id: int, status: Optional[str] = None,
                    order_type: Optional[str] = None, limit: int = 200) -> List[PaperOrder]:
        with self._session() as db:
            q = db.query(PaperOrder).filter(PaperOrder.account_id == account_id)
            if status:
                q = q.filter(PaperOrder.status == status)
            if order_type:
                q = q.filter(PaperOrder.order_type == order_type)
            return q.order_by(PaperOrder.created_at.desc()).limit(limit).all()

    def list_pending(self, account_id: Optional[int] = None, limit: int = 500) -> List[PaperOrder]:
        """列出待成交 / 部分成交的订单（后台重试撮合用）。"""
        with self._session() as db:
            q = db.query(PaperOrder).filter(PaperOrder.status.in_(["pending", "partial"]))
            if account_id is not None:
                q = q.filter(PaperOrder.account_id == account_id)
            return q.order_by(PaperOrder.created_at.asc()).limit(limit).all()

    def list_children(self, parent_id: int) -> List[PaperOrder]:
        with self._session() as db:
            return (
                db.query(PaperOrder)
                .filter(PaperOrder.parent_id == parent_id)
                .order_by(PaperOrder.created_at.asc())
                .all()
            )
