"""模拟盘交易系统 — 账户仓储。"""
from typing import List, Optional

from app.paper.domain_models import User, PaperAccount, PaperPosition
from app.paper.repositories.base import BaseRepository


class AccountRepository(BaseRepository):
    """用户与模拟账户的持久化。"""

    model = PaperAccount

    def get_or_create_user(self, username: str) -> User:
        with self._session() as db:
            user = db.query(User).filter(User.username == username).first()
            if user:
                return user
            user = User(username=username, nickname=username)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    def find_user(self, username: str) -> Optional[User]:
        with self._session() as db:
            return db.query(User).filter(User.username == username).first()

    def create_account(self, user_id: int, name: str, initial_capital: float) -> PaperAccount:
        with self._session() as db:
            acct = PaperAccount(
                user_id=user_id,
                name=name,
                initial_capital=initial_capital,
                cash=initial_capital,
                available_cash=initial_capital,
                total_assets=initial_capital,
            )
            db.add(acct)
            db.commit()
            db.refresh(acct)
            return acct

    def get_account(self, account_id: int) -> Optional[PaperAccount]:
        return self.get(account_id)

    def list_accounts(self, user_id: Optional[int] = None) -> List[PaperAccount]:
        with self._session() as db:
            q = db.query(PaperAccount)
            if user_id is not None:
                q = q.filter(PaperAccount.user_id == user_id)
            return q.order_by(PaperAccount.created_at.desc()).all()

    def list_positions(self, account_id: int) -> List[PaperPosition]:
        with self._session() as db:
            return (
                db.query(PaperPosition)
                .filter(PaperPosition.account_id == account_id)
                .all()
            )

    def update_metrics(self, account_id: int, **fields) -> PaperAccount:
        return self.update(account_id, **fields)
