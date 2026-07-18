"""模拟盘交易系统 — 账户服务（Service Layer）。

职责：账户创建 / 查询 / 列表，以及账户实时指标的计算编排。
指标计算逻辑下沉到 metrics_service，本层只做编排与协议转换（ORM → 响应模型）。
"""
from typing import List, Optional

from app.paper.domain_models import PaperAccount, PaperPosition
from app.paper.repositories.account_repo import AccountRepository
from app.paper.schemas import (
    CreateAccountRequest,
    AccountResponse,
    AccountMetricsResponse,
    AccountOverviewResponse,
    AccountOverviewItem,
    UpdateAccountRequest,
)
from app.paper.services.metrics_service import compute_account_metrics
from app.paper.errors import PaperError

# 初始资金预设档位（元）
CAPITAL_PRESETS = {
    "100万": 1_000_000.0,
    "500万": 5_000_000.0,
    "1000万": 10_000_000.0,
}


class AccountService:
    def __init__(self):
        self.repo = AccountRepository()

    # —— 创建 ——
    def create_account(self, req: CreateAccountRequest) -> AccountResponse:
        initial = self._resolve_capital(req)
        user = self.repo.get_or_create_user(req.username)
        acct = self.repo.create_account(user.id, req.name, initial)
        return self._to_response(acct, positions=[])

    # —— 查询 ——
    def get_account(self, account_id: int) -> AccountResponse:
        acct, positions = self._load(account_id)
        return self._to_response(acct, positions)

    def get_metrics(self, account_id: int) -> AccountMetricsResponse:
        acct, positions = self._load(account_id)
        return AccountMetricsResponse(**compute_account_metrics(acct, positions))

    def list_accounts(self, username: Optional[str] = None) -> List[AccountResponse]:
        user_id = None
        if username:
            user = self.repo.find_user(username)
            if user:
                user_id = user.id
        accounts = self.repo.list_accounts(user_id)
        return [self._to_response(a, positions=[]) for a in accounts]

    # —— 更新 ——
    def update_account(self, account_id: int, req: UpdateAccountRequest) -> AccountResponse:
        acct = self.repo.get_account(account_id)
        if not acct:
            raise PaperError(f"账户不存在: {account_id}", "ACCOUNT_NOT_FOUND")
        updates = {}
        if req.name is not None:
            updates["name"] = req.name
        if req.initialCapital is not None and req.initialCapital > 0:
            diff = req.initialCapital - acct.initial_capital
            updates["initial_capital"] = req.initialCapital
            updates["cash"] = acct.cash + diff
            updates["total_assets"] = (acct.total_assets or 0) + diff
            updates["available_cash"] = (acct.available_cash or 0) + diff
        if updates:
            self.repo.update(account_id, **updates)
        acct, positions = self._load(account_id)
        return self._to_response(acct, positions)

    # —— 删除 ——
    def delete_account(self, account_id: int) -> bool:
        acct = self.repo.get_account(account_id)
        if not acct:
            raise PaperError(f"账户不存在: {account_id}", "ACCOUNT_NOT_FOUND")
        # 级联清理关联数据
        from app.paper.repositories.base import BaseRepository
        from app.paper.domain_models import (
            PaperOrder, PaperPosition, PaperStrategy,
            PaperRiskConfig, PaperRiskEvent, PaperPoolConfig,
            PaperPortfolio, PaperResearchSession,
        )
        base = BaseRepository()
        for model in [PaperOrder, PaperPosition, PaperStrategy,
                       PaperRiskConfig, PaperRiskEvent, PaperPoolConfig,
                       PaperPortfolio, PaperResearchSession]:
            base.model = model
            objs = base.filter_by(account_id=account_id)
            for o in objs:
                base.delete(o.id)
        return self.repo.delete(account_id)

    # —— 全账户汇总 ——
    def get_overview(self, username: Optional[str] = None) -> AccountOverviewResponse:
        user_id = None
        if username:
            user = self.repo.find_user(username)
            if user:
                user_id = user.id
        accounts = self.repo.list_accounts(user_id)
        items = []
        total_assets = 0.0
        total_pnl = 0.0
        total_pos_val = 0.0
        total_cash = 0.0
        active = 0
        for a in accounts:
            m = compute_account_metrics(a, self.repo.list_positions(a.id))
            total_assets += m["totalAssets"]
            total_pnl += m["totalPnl"]
            total_pos_val += m["positionValue"]
            total_cash += a.cash or 0
            if a.status == "active":
                active += 1
            items.append(AccountOverviewItem(
                id=a.id, name=a.name,
                totalAssets=m["totalAssets"],
                totalPnl=m["totalPnl"],
                totalPnlPct=m["totalPnlPct"],
                positionValue=m["positionValue"],
                positionRatio=m["positionRatio"],
                status=a.status,
            ))
        total_init = sum(a.initial_capital for a in accounts) or 1
        total_pnl_pct = round((total_pnl / total_init) * 100, 2)
        return AccountOverviewResponse(
            totalAccounts=len(accounts),
            totalAssets=round(total_assets, 2),
            totalPnl=round(total_pnl, 2),
            totalPnlPct=total_pnl_pct,
            totalPositionValue=round(total_pos_val, 2),
            totalCash=round(total_cash, 2),
            activeCount=active,
            accounts=items,
        )

    # —— 内部 ——
    def _load(self, account_id: int):
        acct = self.repo.get_account(account_id)
        if not acct:
            raise PaperError(f"账户不存在: {account_id}", "ACCOUNT_NOT_FOUND")
        positions = self.repo.list_positions(account_id)
        return acct, positions

    def _resolve_capital(self, req: CreateAccountRequest) -> float:
        if req.preset and req.preset in CAPITAL_PRESETS:
            return CAPITAL_PRESETS[req.preset]
        return req.initialCapital

    def _to_response(self, acct: PaperAccount, positions: List[PaperPosition]) -> AccountResponse:
        m = compute_account_metrics(acct, positions)
        return AccountResponse(
            id=acct.id,
            name=acct.name,
            userId=acct.user_id or 0,
            initialCapital=acct.initial_capital,
            cash=acct.cash,
            frozenCash=acct.frozen_cash,
            totalAssets=m["totalAssets"],
            totalPnl=m["totalPnl"],
            todayPnl=acct.today_pnl,
            totalPnlPct=m["totalPnlPct"],
            positionValue=m["positionValue"],
            availableCash=m["availableCash"],
            positionRatio=m["positionRatio"],
            maxDrawdown=acct.max_drawdown,
            sharpeRatio=acct.sharpe_ratio,
            winRate=acct.win_rate,
            profitLossRatio=acct.profit_loss_ratio,
            status=acct.status,
            createdAt=acct.created_at.isoformat() if acct.created_at else "",
        )
