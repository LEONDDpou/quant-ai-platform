"""模拟盘交易系统 — M7 AI 自动交易仓储。

围绕 AI 自动交易所需的四类持久化对象：
- PaperStrategy  策略配置（启用开关 / 参数 / 绩效）
- Signal         生成的买卖/持有信号
- TradeLog       AI 决策 / 交易日志（log_type 以 ai_ 前缀）
- Watchlist      监控标的池（策略缺省 universe 来源）
"""
from typing import List, Optional

from app.paper.domain_models import (
    PaperStrategy,
    Signal,
    TradeLog,
    Watchlist,
)
from app.paper.repositories.base import BaseRepository


class StrategyRepository(BaseRepository):
    """AI 交易策略配置（PaperStrategy）持久化。"""

    model = PaperStrategy

    def list_by_account(self, account_id: int) -> List[PaperStrategy]:
        with self._session() as db:
            return (
                db.query(PaperStrategy)
                .filter(PaperStrategy.account_id == account_id)
                .order_by(PaperStrategy.created_at.desc())
                .all()
            )

    def get_by_account(self, account_id: int, strategy_id: str) -> Optional[PaperStrategy]:
        with self._session() as db:
            return (
                db.query(PaperStrategy)
                .filter(PaperStrategy.account_id == account_id,
                        PaperStrategy.id == strategy_id)
                .first()
            )

    def enabled_for_account(self, account_id: int) -> List[PaperStrategy]:
        with self._session() as db:
            return (
                db.query(PaperStrategy)
                .filter(PaperStrategy.account_id == account_id,
                        PaperStrategy.enabled == True)  # noqa: E712
                .order_by(PaperStrategy.created_at.asc())
                .all()
            )


class SignalRepository(BaseRepository):
    """交易信号（Signal）持久化。"""

    model = Signal

    def add_signal(self, sig: Signal) -> Signal:
        return self.add(sig)

    def list_recent(self, account_id: int, limit: int = 50,
                    code: Optional[str] = None) -> List[Signal]:
        with self._session() as db:
            q = db.query(Signal).filter(Signal.account_id == account_id)
            if code:
                q = q.filter(Signal.code == code)
            return q.order_by(Signal.created_at.desc()).limit(limit).all()


class AILogRepository(BaseRepository):
    """AI 日志（TradeLog，log_type 以 ai_ 前缀）持久化。"""

    def add_log(self, account_id: int, log_type: str, level: str,
                message: str, meta: Optional[dict] = None) -> int:
        with self._session() as db:
            log = TradeLog(
                account_id=account_id, log_type=log_type,
                level=level, message=message, meta=meta or {},
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return log.id

    def list_recent(self, account_id: int, limit: int = 50,
                    log_type: Optional[str] = None) -> List[TradeLog]:
        with self._session() as db:
            q = db.query(TradeLog).filter(TradeLog.account_id == account_id)
            if log_type:
                q = q.filter(TradeLog.log_type == log_type)
            return q.order_by(TradeLog.created_at.desc()).limit(limit).all()


class WatchlistRepository(BaseRepository):
    """自选股（监控池）持久化 —— 作为 AI 策略缺省 universe 来源。"""

    model = Watchlist

    def list_codes(self, account_id: int) -> List[str]:
        with self._session() as db:
            rows = db.query(Watchlist).filter(Watchlist.account_id == account_id).all()
            return [r.code for r in rows]
