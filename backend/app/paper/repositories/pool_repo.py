"""模拟盘交易系统 — M179 股票池自动维护仓储层。

围绕股票池自动维护的三类持久化对象：
- Watchlist          股票池标的（扩展 pinned/category/health/last_checked/source）
- PaperPoolConfig    账户级自动维护配置（同步源 / 自动移除规则）
- PaperPoolChangeLog 股票池变更日志（同步新增 / 自动移除留痕）
"""
from typing import List, Optional

from app.paper.domain_models import (
    PaperPoolChangeLog,
    PaperPoolConfig,
    Watchlist,
)
from app.paper.repositories.base import BaseRepository
from app.paper.errors import PaperError


class PoolItemRepository(BaseRepository):
    """股票池标的（Watchlist）持久化。"""

    model = Watchlist

    def list_items(self, account_id: int) -> List[Watchlist]:
        """列出账户全部股票池标的（按 id 升序）。"""
        with self._session() as db:
            return (
                db.query(Watchlist)
                .filter(Watchlist.account_id == account_id)
                .order_by(Watchlist.id.asc())
                .all()
            )

    def get_by_code(self, account_id: int, code: str) -> Optional[Watchlist]:
        with self._session() as db:
            return (
                db.query(Watchlist)
                .filter(Watchlist.account_id == account_id, Watchlist.code == code)
                .first()
            )

    def add(self, item: Watchlist) -> Watchlist:
        with self._session() as db:
            db.add(item)
            db.commit()
            db.refresh(item)
            return item

    def delete(self, pk) -> bool:  # 重写以返回 bool（基类亦返回 bool）
        with self._session() as db:
            obj = db.get(self.model, pk)
            if not obj:
                return False
            db.delete(obj)
            db.commit()
            return True


class PoolConfigRepository(BaseRepository):
    """股票池自动维护配置（每账户一条）持久化。"""

    model = PaperPoolConfig

    def get_by_account(self, account_id: int) -> Optional[PaperPoolConfig]:
        with self._session() as db:
            return (
                db.query(PaperPoolConfig)
                .filter(PaperPoolConfig.account_id == account_id)
                .first()
            )

    def upsert(self, account_id: int, **fields) -> PaperPoolConfig:
        with self._session() as db:
            obj = (
                db.query(PaperPoolConfig)
                .filter(PaperPoolConfig.account_id == account_id)
                .first()
            )
            if obj is None:
                obj = PaperPoolConfig(account_id=account_id)
                db.add(obj)
            for k, v in fields.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            db.commit()
            db.refresh(obj)
            return obj


class PoolChangeLogRepository(BaseRepository):
    """股票池变更日志持久化。"""

    model = PaperPoolChangeLog

    def add(self, log: PaperPoolChangeLog) -> PaperPoolChangeLog:
        with self._session() as db:
            db.add(log)
            db.commit()
            db.refresh(log)
            return log

    def list_recent(self, account_id: int, limit: int = 100) -> List[PaperPoolChangeLog]:
        with self._session() as db:
            return (
                db.query(PaperPoolChangeLog)
                .filter(PaperPoolChangeLog.account_id == account_id)
                .order_by(PaperPoolChangeLog.id.desc())
                .limit(limit)
                .all()
            )
