"""模拟盘交易系统 — 持仓服务（Service Layer）。

职责：
- 持仓变更（买入建仓 / 卖出减仓），由撮合引擎在「同一数据库事务」内调用，
  保证 账户现金 ↔ 持仓 ↔ 订单 ↔ 成交 的原子性；
- 成本价采用「移动加权平均」；
- T+1：当日买入股份不计入可卖数量（sellable_shares 表示前日持仓）；
- 持仓指标（市值 / 盈亏 / 仓位比例 / 持仓天数）实时计算；
- 日终滚动（rollover_day）：将当日买入转为可卖，持仓天数 +1。

注意：本服务的持仓「变更」方法接受外部 db 会话（撮合事务内），
查询类方法自行开/关会话，二者互不干扰。
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.paper.domain_models import PaperPosition, PaperTrade
from app.paper.services.position_repo import PositionRepository
from app.paper.repositories.account_repo import AccountRepository
from app.paper.services.market_provider import market_provider
from app.paper.schemas import PositionResponse
from app.paper.errors import PaperError


class PositionService:
    def __init__(self):
        self.repo = PositionRepository()

    # ============================================================
    # 持仓变更（撮合事务内调用，传入 db）
    # ============================================================
    def apply_buy_fill(self, db: Session, account_id: int, code: str, name: str,
                       industry: str, qty: int, fill_price: float, fee: float,
                       trade_time: datetime) -> PaperPosition:
        """买入成交后更新持仓：移动平均成本价，当日买入不计入可卖。"""
        pos = (
            db.query(PaperPosition)
            .filter(PaperPosition.account_id == account_id, PaperPosition.code == code)
            .first()
        )
        if pos is None:
            pos = PaperPosition(
                account_id=account_id, code=code, name=name, industry=industry,
                shares=0, sellable_shares=0, cost_price=0.0, buy_price=fill_price,
                current_price=fill_price, market_value=0.0, pnl_amount=0.0,
                pnl_pct=0.0, hold_days=0, position_ratio=0.0,
            )
            db.add(pos)
            db.flush()

        prev_shares = pos.shares
        new_shares = prev_shares + qty
        # 移动加权平均成本
        if prev_shares == 0:
            pos.cost_price = fill_price
            pos.buy_price = fill_price
        else:
            pos.cost_price = (pos.cost_price * prev_shares + fill_price * qty) / new_shares
        pos.shares = new_shares
        # T+1：当日买入不增加可卖数量（可卖仅含前日持仓）
        pos.current_price = fill_price
        # 重建市值 / 盈亏
        pos.market_value = round(new_shares * fill_price, 2)
        pos.pnl_amount = round((fill_price - pos.cost_price) * new_shares, 2)
        pos.pnl_pct = round((fill_price - pos.cost_price) / pos.cost_price * 100, 2) if pos.cost_price else 0.0
        db.flush()
        return pos

    def apply_sell_fill(self, db: Session, account_id: int, code: str, qty: int,
                        fill_price: float, fee: float, trade_time: datetime) -> tuple[PaperPosition, float]:
        """卖出成交后更新持仓，返回 (持仓, 实现盈亏)。"""
        pos = (
            db.query(PaperPosition)
            .filter(PaperPosition.account_id == account_id, PaperPosition.code == code)
            .first()
        )
        if pos is None:
            raise PaperError(f"持仓不存在，无法卖出: {code}", "POSITION_NOT_FOUND")

        realized = round((fill_price - pos.cost_price) * qty - fee, 2)
        pos.shares -= qty
        pos.sellable_shares = max(0, pos.sellable_shares - qty)
        if pos.shares <= 0:
            # 清仓：删除持仓记录（保留历史可由 trade_logs 追溯）
            db.delete(pos)
            db.flush()
            return None, realized

        pos.current_price = fill_price
        pos.market_value = round(pos.shares * fill_price, 2)
        pos.pnl_amount = round((fill_price - pos.cost_price) * pos.shares, 2)
        pos.pnl_pct = round((fill_price - pos.cost_price) / pos.cost_price * 100, 2) if pos.cost_price else 0.0
        db.flush()
        return pos, realized

    def freeze_sellable(self, db: Session, account_id: int, code: str, qty: int):
        """限价卖挂单时冻结可卖股份（防止重复卖出）。"""
        pos = (
            db.query(PaperPosition)
            .filter(PaperPosition.account_id == account_id, PaperPosition.code == code)
            .first()
        )
        if pos:
            pos.sellable_shares = max(0, pos.sellable_shares - qty)
            db.flush()

    def release_sellable(self, db: Session, account_id: int, code: str, qty: int):
        """撤单 / 部分成交后释放被冻结的可卖股份。"""
        pos = (
            db.query(PaperPosition)
            .filter(PaperPosition.account_id == account_id, PaperPosition.code == code)
            .first()
        )
        if pos:
            pos.sellable_shares += qty
            db.flush()

    def refresh_market_value(self, db: Session, account_id: int, quotes: dict):
        """用最新行情刷新所有持仓的市值 / 盈亏（盘后或定时调用）。"""
        from sqlalchemy import func
        from datetime import date
        from app.paper.domain_models import PaperTrade, PaperAccount
        positions = db.query(PaperPosition).filter(PaperPosition.account_id == account_id).all()
        today_pnl = 0.0
        for pos in positions:
            q = quotes.get(pos.code)
            if q:
                price = q.get("price") or pos.current_price
                pos.current_price = price
                pos.market_value = round(pos.shares * price, 2)
                pos.pnl_amount = round((price - pos.cost_price) * pos.shares, 2)
                pos.pnl_pct = round((price - pos.cost_price) / pos.cost_price * 100, 2) if pos.cost_price else 0.0
                # 当日盈亏 = (现价 - 昨收) × 持仓量
                prev = q.get("prevClose") or q.get("price") or pos.current_price
                today_pnl += (price - prev) * pos.shares
        # 当日已实现盈亏（来自今日成交记录）
        try:
            realized = db.query(func.sum(PaperTrade.realized_pnl)).filter(
                PaperTrade.account_id == account_id,
                PaperTrade.created_at >= date.today(),
            ).scalar() or 0.0
        except Exception:
            realized = 0.0
        acct = db.get(PaperAccount, account_id)
        if acct:
            acct.today_pnl = round(today_pnl + float(realized), 2)
        db.flush()

    # ============================================================
    # 日终滚动（T+1 解锁 + 持仓天数 +1）
    # ============================================================
    def rollover_day(self, account_id: int):
        """将当日买入股份转为可卖，并持仓天数 +1。"""
        with self.repo._session() as db:
            positions = db.query(PaperPosition).filter(PaperPosition.account_id == account_id).all()
            for pos in positions:
                pos.sellable_shares = pos.shares
                pos.hold_days += 1
            db.commit()

    # ============================================================
    # 查询
    # ============================================================
    def get_position(self, account_id: int, code: str) -> Optional[PaperPosition]:
        return self.repo.get_position(account_id, code)

    def list_positions(self, account_id: int) -> List[PositionResponse]:
        """持仓列表（ORM → 响应模型，含仓位比例）。"""
        positions = self.repo.list_positions(account_id)
        acct = AccountRepository().get_account(account_id)
        total_assets = (acct.total_assets or 0.0) if acct else 0.0
        out = []
        for p in positions:
            ratio = (p.market_value / total_assets * 100.0) if total_assets else 0.0
            out.append(PositionResponse(
                accountId=p.account_id, code=p.code, name=p.name, industry=p.industry or "",
                shares=p.shares, sellableShares=p.sellable_shares,
                costPrice=p.cost_price, buyPrice=p.buy_price, currentPrice=p.current_price,
                marketValue=p.market_value, pnlAmount=p.pnl_amount, pnlPct=p.pnl_pct,
                holdDays=p.hold_days, positionRatio=round(ratio, 2),
                stopLossPrice=p.stop_loss_price or 0.0,
                takeProfitPrice=p.take_profit_price or 0.0,
            ))
        return out

    # ============================================================
    # 持仓汇总（M4：盈亏分析 / 集中度 / 行业分布）
    # ============================================================
    def _realized_pnl(self, account_id: int) -> float:
        """累计已实现盈亏（来自成交记录）。"""
        with self.repo._session() as db:
            rows = db.query(PaperTrade).filter(PaperTrade.account_id == account_id).all()
            return round(sum(r.realized_pnl or 0.0 for r in rows), 2)

    def get_summary(self, account_id: int) -> dict:
        """持仓汇总：市值/成本/浮动盈亏/已实现盈亏/当日盈亏/集中度/行业分布。

        当日盈亏基于实时行情的「昨收」计算；集中度相对账户总资产。
        """
        positions = self.repo.list_positions(account_id)
        acct = AccountRepository().get_account(account_id)
        total_assets = (acct.total_assets or 0.0) if acct else 0.0

        total_mv = sum(p.market_value for p in positions)
        total_cost = sum(p.cost_price * p.shares for p in positions)
        unrealized = sum(p.pnl_amount for p in positions)

        # 集中度（相对总资产）
        ratios = [(p.market_value / total_assets * 100.0) if total_assets else 0.0 for p in positions]
        max_ratio = max(ratios) if ratios else 0.0
        top3 = sum(sorted(ratios, reverse=True)[:3])

        # 当日盈亏：基于实时行情昨收
        today = 0.0
        for p in positions:
            q = market_provider.quote(p.code)
            prev = q.get("prevClose") or q.get("price") or p.current_price
            today += (p.current_price - prev) * p.shares

        realized = self._realized_pnl(account_id)
        unrealized_pct = (unrealized / total_cost * 100.0) if total_cost else 0.0
        base_today = total_mv - today
        today_pct = (today / base_today * 100.0) if base_today else 0.0
        total_pnl = unrealized + realized

        # 行业分布
        ind: dict[str, float] = {}
        for p in positions:
            key = p.industry or "未知"
            ind[key] = ind.get(key, 0.0) + p.market_value
        industry_distribution = [
            {
                "industry": k,
                "marketValue": round(v, 2),
                "ratio": round(v / total_mv * 100.0, 2) if total_mv else 0.0,
            }
            for k, v in sorted(ind.items(), key=lambda x: -x[1])
        ]

        return {
            "accountId": account_id,
            "positionCount": len(positions),
            "totalMarketValue": round(total_mv, 2),
            "totalCost": round(total_cost, 2),
            "unrealizedPnl": round(unrealized, 2),
            "unrealizedPnlPct": round(unrealized_pct, 2),
            "realizedPnl": round(realized, 2),
            "todayPnl": round(today, 2),
            "todayPnlPct": round(today_pct, 2),
            "totalPnl": round(total_pnl, 2),
            "maxPositionRatio": round(max_ratio, 2),
            "top3Ratio": round(top3, 2),
            "industryDistribution": industry_distribution,
        }

    def refresh_market_value_public(self, account_id: int) -> List[PositionResponse]:
        """用实时行情刷新全部持仓市值/盈亏，返回刷新后的持仓列表。"""
        with self.repo._session() as db:
            positions = db.query(PaperPosition).filter(PaperPosition.account_id == account_id).all()
            quotes = {pos.code: market_provider.quote(pos.code) for pos in positions}
            self.refresh_market_value(db, account_id, quotes)
            db.commit()
        return self.list_positions(account_id)
