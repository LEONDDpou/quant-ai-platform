"""模拟盘交易系统 — 权益快照仓储（M6）。

遵循项目统一的 Repository 模式（与 risk_repo / order_repo 一致），
所有方法在独立 Session 内完成，避免长事务与连接泄漏。
"""
from typing import List, Optional

from app.paper.domain_models import PaperEquitySnapshot
from app.paper.repositories.base import BaseRepository


class EquitySnapshotRepository(BaseRepository):
    """日级权益快照仓储。按账户 + 日期幂等存取。"""

    model = PaperEquitySnapshot

    def get_by_account_date(self, account_id: int, date: str) -> Optional[PaperEquitySnapshot]:
        with self._session() as db:
            return (
                db.query(PaperEquitySnapshot)
                .filter(
                    PaperEquitySnapshot.account_id == account_id,
                    PaperEquitySnapshot.date == date,
                )
                .first()
            )

    def prev_snapshot(self, account_id: int, date: str) -> Optional[PaperEquitySnapshot]:
        """返回日期早于 date 的最新一条快照（用于计算当日盈亏）。"""
        with self._session() as db:
            return (
                db.query(PaperEquitySnapshot)
                .filter(
                    PaperEquitySnapshot.account_id == account_id,
                    PaperEquitySnapshot.date < date,
                )
                .order_by(PaperEquitySnapshot.date.desc())
                .first()
            )

    def list_by_account(self, account_id: int, limit: Optional[int] = None) -> List[PaperEquitySnapshot]:
        with self._session() as db:
            q = (
                db.query(PaperEquitySnapshot)
                .filter(PaperEquitySnapshot.account_id == account_id)
                .order_by(PaperEquitySnapshot.date.asc())
            )
            if limit:
                q = q.limit(limit)
            return q.all()

    def upsert(self, account_id: int, date: str, **fields) -> PaperEquitySnapshot:
        with self._session() as db:
            row = (
                db.query(PaperEquitySnapshot)
                .filter(
                    PaperEquitySnapshot.account_id == account_id,
                    PaperEquitySnapshot.date == date,
                )
                .first()
            )
            if row is None:
                row = PaperEquitySnapshot(account_id=account_id, date=date)
                db.add(row)
            for k, v in fields.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            db.commit()
            db.refresh(row)
            return row

    def delete_by_account(self, account_id: int) -> int:
        with self._session() as db:
            n = (
                db.query(PaperEquitySnapshot)
                .filter(PaperEquitySnapshot.account_id == account_id)
                .delete()
            )
            db.commit()
            return n
