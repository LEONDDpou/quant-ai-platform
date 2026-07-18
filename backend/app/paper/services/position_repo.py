"""模拟盘交易系统 — 持仓仓储。

持仓的「变更」逻辑（买入建仓、卖出减仓、成本价移动平均、T+1 可卖数量）放在
position_service（与撮合在同一事务内调用）；本仓储只负责持久化读写。
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.paper.domain_models import PaperPosition
from app.paper.repositories.base import BaseRepository
from app.paper.errors import PaperError


class PositionRepository(BaseRepository):
    """持仓持久化。"""

    model = PaperPosition

    def get_position(self, account_id: int, code: str) -> Optional[PaperPosition]:
        with self._session() as db:
            return (
                db.query(PaperPosition)
                .filter(PaperPosition.account_id == account_id, PaperPosition.code == code)
                .first()
            )

    def list_positions(self, account_id: int) -> List[PaperPosition]:
        with self._session() as db:
            return (
                db.query(PaperPosition)
                .filter(PaperPosition.account_id == account_id)
                .order_by(PaperPosition.market_value.desc())
                .all()
            )

    def create_position(self, account_id: int, code: str, name: str = "", industry: str = "") -> PaperPosition:
        with self._session() as db:
            pos = PaperPosition(
                account_id=account_id, code=code, name=name, industry=industry,
                shares=0, sellable_shares=0, cost_price=0.0, buy_price=0.0,
                current_price=0.0, market_value=0.0, pnl_amount=0.0,
                pnl_pct=0.0, hold_days=0, position_ratio=0.0,
            )
            db.add(pos)
            db.commit()
            db.refresh(pos)
            return pos

    def update(self, pk, **fields):  # type: ignore[override]
        return super().update(pk, **fields)

    def delete_position(self, account_id: int, code: str) -> bool:
        with self._session() as db:
            pos = (
                db.query(PaperPosition)
                .filter(PaperPosition.account_id == account_id, PaperPosition.code == code)
                .first()
            )
            if not pos:
                return False
            db.delete(pos)
            db.commit()
            return True
