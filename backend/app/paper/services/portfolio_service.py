"""策略组合服务层（#184）。

能力：组合 CRUD、策略分配、一键运行所有策略、再平衡（更新分配+触发运行）。
"""
import json
from datetime import datetime
from typing import List, Optional

from app.paper.domain_models import (
    PaperPortfolio,
    PaperPortfolioRebalance,
)
from app.paper.errors import PaperError
from app.paper.repositories.base import BaseRepository
from app.paper.schemas import (
    PortfolioAllocation,
    PortfolioRebalanceResponse,
    PortfolioRequest,
    PortfolioResponse,
)


class _PortfolioRepo(BaseRepository):
    model = PaperPortfolio


class _RebalanceRepo(BaseRepository):
    model = PaperPortfolioRebalance


class PortfolioService:
    """组合管理服务。"""

    def __init__(self):
        self.repo = _PortfolioRepo()
        self.rb_repo = _RebalanceRepo()

    def list_portfolios(self, account_id: int) -> List[PortfolioResponse]:
        objs = self.repo.filter_by(account_id=account_id)
        return [self._to_resp(o) for o in objs]

    def get_portfolio(self, portfolio_id: int) -> Optional[PortfolioResponse]:
        obj = self.repo.get(portfolio_id)
        if not obj:
            return None
        return self._to_resp(obj)

    def create_portfolio(self, req: PortfolioRequest) -> PortfolioResponse:
        alloc = {a.strategyId: a.weight for a in req.allocation}
        obj = PaperPortfolio(
            account_id=req.accountId,
            name=req.name,
            description=req.description,
            allocation=alloc,
            total_capital=req.totalCapital,
            enabled=req.enabled,
        )
        self.repo.add(obj)
        return self._to_resp(obj)

    def update_portfolio(self, portfolio_id: int, req: PortfolioRequest) -> PortfolioResponse:
        with self.repo._session() as db:
            obj = db.get(PaperPortfolio, portfolio_id)
            if not obj:
                raise PaperError("组合不存在")
            obj.name = req.name
            obj.description = req.description
            obj.allocation = {a.strategyId: a.weight for a in req.allocation}
            obj.total_capital = req.totalCapital
            obj.enabled = req.enabled
            db.commit()
            db.refresh(obj)
            return self._to_resp(obj)

    def delete_portfolio(self, portfolio_id: int) -> bool:
        return self.repo.delete(portfolio_id)

    def run_portfolio(self, portfolio_id: int) -> dict:
        """运行组合中的所有启用的策略。调用 AutoTradeService.run_once 逐一执行。"""
        obj = self.repo.get(portfolio_id)
        if not obj:
            raise PaperError("组合不存在")
        if not obj.enabled:
            raise PaperError("组合已禁用")
        if not obj.allocation:
            raise PaperError("组合未分配任何策略")

        from app.paper.services.auto_trade_service import AutoTradeService
        at = AutoTradeService()
        results = {}
        for strategy_id in obj.allocation:
            try:
                at.run_once(obj.account_id, strategy_id=strategy_id)
                results[strategy_id] = "ok"
            except Exception as e:
                results[strategy_id] = f"error: {e}"
        return {"portfolioId": portfolio_id, "strategyResults": results}

    def rebalance(self, portfolio_id: int, req: PortfolioRequest, reason: str = "") -> PortfolioRebalanceResponse:
        """组合再平衡：保存旧分配 → 更新新分配 → 触发运行。"""
        with self.repo._session() as db:
            obj = db.get(PaperPortfolio, portfolio_id)
            if not obj:
                raise PaperError("组合不存在")
            before = obj.allocation or {}
            after = {a.strategyId: a.weight for a in req.allocation}
            obj.allocation = after
            obj.total_capital = req.totalCapital
            db.flush()

            rb = PaperPortfolioRebalance(
                portfolio_id=portfolio_id,
                reason=reason or "手动再平衡",
                allocations_before=before,
                allocations_after=after,
                status="done",
            )
            db.add(rb)
            db.commit()
            rb_resp = self._rb_to_resp(rb)

        # 触发运行
        try:
            self.run_portfolio(portfolio_id)
        except Exception:
            pass

        return rb_resp

    def list_rebalances(self, portfolio_id: int, limit: int = 20) -> List[PortfolioRebalanceResponse]:
        objs = self.rb_repo.filter_by(portfolio_id=portfolio_id)
        return [self._rb_to_resp(o) for o in objs[:limit]]

    # —— helpers ——

    def _to_resp(self, obj: PaperPortfolio) -> PortfolioResponse:
        alloc_list = []
        if obj.allocation:
            for sid, w in obj.allocation.items():
                alloc_list.append(PortfolioAllocation(strategyId=sid, weight=float(w)))
        return PortfolioResponse(
            id=obj.id,
            accountId=obj.account_id,
            name=obj.name or "",
            description=obj.description or "",
            allocation=alloc_list,
            totalCapital=obj.total_capital or 0.0,
            enabled=obj.enabled if obj.enabled is not None else True,
            strategyCount=len(alloc_list),
            createdAt=obj.created_at.isoformat() if obj.created_at else "",
            updatedAt=obj.updated_at.isoformat() if obj.updated_at else "",
        )

    def _rb_to_resp(self, obj: PaperPortfolioRebalance) -> PortfolioRebalanceResponse:
        def _alloc_list(d):
            if isinstance(d, dict):
                return [{"strategyId": k, "weight": float(v)} for k, v in d.items()]
            return []
        return PortfolioRebalanceResponse(
            id=obj.id,
            portfolioId=obj.portfolio_id,
            triggeredAt=obj.triggered_at.isoformat() if obj.triggered_at else "",
            reason=obj.reason or "",
            allocationsBefore=_alloc_list(obj.allocations_before),
            allocationsAfter=_alloc_list(obj.allocations_after),
            status=obj.status or "done",
            notes=obj.notes or "",
        )
