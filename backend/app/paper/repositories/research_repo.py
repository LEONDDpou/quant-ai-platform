"""研究员 Agent 仓储层（Repository Pattern）。

三个仓储，分别对应一次研究会话 / 因子结论 / 策略想法：
- ResearchSessionRepository  ：研究会话的创建与按账户列举；
- FactorFindingRepository    ：因子结论的写入与按会话列举；
- StrategyIdeaRepository     ：策略想法的 CRUD + 回测关联。

全部继承 BaseRepository，复用通用 CRUD；写操作异常向上抛 PaperError，
由服务层/路由层统一转换；读操作失败返回 None / 空列表。
"""
from typing import Optional

from app.db.database import SessionLocal
from app.paper.domain_models import (
    PaperResearchSession,
    PaperFactorFinding,
    PaperStrategyIdea,
)
from app.paper.errors import PaperError
from app.paper.repositories.base import BaseRepository


class ResearchSessionRepository(BaseRepository):
    """研究会话仓储。"""

    model = PaperResearchSession

    def list_sessions(self, account_id: Optional[int] = None, limit: int = 50):
        """按账户列举会话（账户为 None 时含全局会话）；默认倒序。"""
        with self._session() as db:
            q = db.query(PaperResearchSession)
            if account_id is not None:
                q = q.filter(
                    (PaperResearchSession.account_id == account_id)
                    | (PaperResearchSession.account_id.is_(None))
                )
            return q.order_by(PaperResearchSession.id.desc()).limit(limit).all()

    def get_session(self, session_id: int):
        return self.get(session_id)


class FactorFindingRepository(BaseRepository):
    """因子结论仓储。"""

    model = PaperFactorFinding

    def list_by_session(self, session_id: int):
        with self._session() as db:
            return (
                db.query(PaperFactorFinding)
                .filter(PaperFactorFinding.session_id == session_id)
                .order_by(PaperFactorFinding.id.asc())
                .all()
            )


class StrategyIdeaRepository(BaseRepository):
    """策略想法仓储。"""

    model = PaperStrategyIdea

    def list_ideas(self, account_id: Optional[int] = None, limit: int = 100):
        """按账户列举策略想法（账户为 None 时含全局想法）；默认倒序。"""
        with self._session() as db:
            q = db.query(PaperStrategyIdea)
            if account_id is not None:
                q = q.filter(
                    (PaperStrategyIdea.account_id == account_id)
                    | (PaperStrategyIdea.account_id.is_(None))
                )
            return q.order_by(PaperStrategyIdea.id.desc()).limit(limit).all()

    def get_idea(self, idea_id: int):
        return self.get(idea_id)

    def mark_backtested(self, idea_id: int, run_id: int):
        """关联回测结果并标记已回测。"""
        return self.update(idea_id, backtest_run_id=run_id, backtested=True)

    def delete_idea(self, idea_id: int) -> bool:
        return self.delete(idea_id)
