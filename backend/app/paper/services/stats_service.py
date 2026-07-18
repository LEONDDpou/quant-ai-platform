"""模拟盘交易系统 — 资金与收益曲线 / 统计中心（M6）。

职责：
1. 日级权益快照（PaperEquitySnapshot）：记录账户每日收盘权益、现金、持仓市值、
   当日盈亏、累计盈亏，构成收益曲线；
2. 由快照序列驱动 M1 预留的 max_drawdown / sharpe_ratio 字段；
3. 由成交记录（已实现盈亏的平仓单）驱动 win_rate / profit_loss_ratio；
4. refresh 将统计结果写回账户表，供 AccountService 指标接口与前端账户卡片展示。

设计要点：
- 快照按「账户 + 日期」幂等 upsert；日期为本地交易日（YYYY-MM-DD）。
- 权益 = 现金 + 实时行情刷新的持仓市值；快照当下用最新行情，历史日无法回算。
- 收益曲线随时间累积；首帧由 seed_baseline 注入「建仓日=初始资金」基线，使曲线可见。
- 交易统计以「每笔平仓（卖出成交）」为最小交易单元（含部分平仓），
  胜率 = 盈利平仓数 / 平仓总数。这是清晰、可复现的定义，不依赖复杂的 FIFO 配对。
"""
from datetime import datetime
from typing import List, Optional

from app.paper.domain_models import PaperTrade
from app.paper.repositories.account_repo import AccountRepository
from app.paper.services.position_service import PositionService
from app.paper.services.stats_repo import EquitySnapshotRepository
from app.paper.errors import PaperError

# 年化因子：A股约 242 个交易日/年（取 252 通用值）
PERIODS_PER_YEAR = 252
# 无风险利率（年化），演示取 0
_RF_ANNUAL = 0.0


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class StatsService:
    """资金与收益曲线 / 统计中心服务（M6）。"""

    def __init__(self):
        self.snap_repo = EquitySnapshotRepository()
        self.pos_svc = PositionService()

    # ——————————————————————— 权益快照 ———————————————————————
    def equity_now(self, account_id: int):
        """计算账户当前权益（刷新持仓市值到最新行情）。返回 (cash, position_value, total_assets)。"""
        acct = AccountRepository().get_account(account_id)
        if not acct:
            raise PaperError(f"账户不存在: {account_id}", "ACCOUNT_NOT_FOUND")
        positions = self.pos_svc.refresh_market_value_public(account_id)  # list[PositionResponse]
        position_value = sum(p.marketValue for p in positions)
        cash = acct.cash or 0.0
        total = cash + position_value
        return cash, position_value, total

    def take_snapshot(self, account_id: int, date: Optional[str] = None) -> object:
        """对指定日期（默认今日）做一次权益快照，幂等 upsert。返回 PaperEquitySnapshot。"""
        date = date or _today_str()
        cash, position_value, total = self.equity_now(account_id)
        acct = AccountRepository().get_account(account_id)
        initial = acct.initial_capital or 0.0

        # 前一交易日快照（日期 < 今日）用于计算当日盈亏；无前序则相对初始资金
        prev = self.snap_repo.prev_snapshot(account_id, date)
        prev_total = prev.total_assets if prev else initial
        daily_pnl = total - prev_total
        daily_pnl_pct = (daily_pnl / prev_total * 100.0) if prev_total else 0.0
        cumulative_pnl = total - initial
        cumulative_pnl_pct = (cumulative_pnl / initial * 100.0) if initial else 0.0

        return self.snap_repo.upsert(
            account_id, date,
            total_assets=round(total, 2), cash=round(cash, 2),
            position_value=round(position_value, 2),
            daily_pnl=round(daily_pnl, 2), daily_pnl_pct=round(daily_pnl_pct, 2),
            cumulative_pnl=round(cumulative_pnl, 2),
            cumulative_pnl_pct=round(cumulative_pnl_pct, 2),
        )

    def seed_baseline(self, account_id: int) -> Optional[object]:
        """注入建仓日基线快照（初始资金）。仅当该账户无任何快照时执行。返回新增快照或 None。"""
        if self.snap_repo.list_by_account(account_id):
            return None
        acct = AccountRepository().get_account(account_id)
        if not acct:
            raise PaperError(f"账户不存在: {account_id}", "ACCOUNT_NOT_FOUND")
        base_date = (acct.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
        return self.snap_repo.upsert(
            account_id, base_date,
            total_assets=round(acct.initial_capital, 2),
            cash=round(acct.initial_capital, 2),
            position_value=0.0, daily_pnl=0.0, daily_pnl_pct=0.0,
            cumulative_pnl=0.0, cumulative_pnl_pct=0.0,
        )

    def get_equity_curve(self, account_id: int, days: Optional[int] = None) -> List[dict]:
        snaps = self.snap_repo.list_by_account(account_id, limit=days)
        return [
            {
                "date": s.date,
                "totalAssets": s.total_assets,
                "cash": s.cash,
                "positionValue": s.position_value,
                "dailyPnl": s.daily_pnl,
                "dailyPnlPct": s.daily_pnl_pct,
                "cumulativePnl": s.cumulative_pnl,
                "cumulativePnlPct": s.cumulative_pnl_pct,
            }
            for s in snaps
        ]

    # ——————————————————————— 统计指标 ———————————————————————
    @staticmethod
    def _max_drawdown(values: List[float]) -> float:
        """基于权益序列的最大回撤（%，正数表示回撤幅度）。"""
        if len(values) < 2:
            return 0.0
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100.0 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 2)

    @staticmethod
    def _sharpe(values: List[float]) -> float:
        """基于相邻权益收益率的夏普比率（年化，无风险利率取 0）。"""
        if len(values) < 2:
            return 0.0
        rets: List[float] = []
        for i in range(1, len(values)):
            prev = values[i - 1]
            if prev and prev > 0:
                rets.append(values[i] / prev - 1.0)
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        std = var ** 0.5
        if std == 0:
            return 0.0
        return round((mean / std) * (PERIODS_PER_YEAR ** 0.5), 3)

    def _trade_stats(self, account_id: int) -> dict:
        """交易统计：以每笔平仓（卖出成交）为交易单元。"""
        with self.snap_repo._session() as db:
            sells = (
                db.query(PaperTrade)
                .filter(PaperTrade.account_id == account_id, PaperTrade.direction == "sell")
                .all()
            )
        pnls = [float(t.realized_pnl or 0.0) for t in sells]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        trade_count = len(pnls)
        win_count = len(wins)
        loss_count = len(losses)
        avg_win = (sum(wins) / len(wins)) if wins else 0.0
        # 平均亏损以正数（亏损额绝对值）表示，便于「盈利/亏损」直接相除
        avg_loss = (abs(sum(losses) / len(losses))) if losses else 0.0
        win_rate = (win_count / trade_count * 100.0) if trade_count else 0.0
        # 无亏损记录时盈亏比记为 0（N/A），避免除以 0 与无意义无穷大
        pl_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
        return {
            "tradeCount": trade_count,
            "winCount": win_count,
            "lossCount": loss_count,
            "avgWin": round(avg_win, 2),
            "avgLoss": round(avg_loss, 2),
            "winRate": round(win_rate, 2),
            "profitLossRatio": round(pl_ratio, 2),
        }

    def get_statistics(self, account_id: int) -> dict:
        """汇总收益曲线 + 交易统计。不写回账户表。"""
        acct = AccountRepository().get_account(account_id)
        if not acct:
            raise PaperError(f"账户不存在: {account_id}", "ACCOUNT_NOT_FOUND")
        curve = self.get_equity_curve(account_id)
        values = [c["totalAssets"] for c in curve]
        initial = acct.initial_capital or 0.0
        # 无快照时回退到账户实时总资产（含持仓），避免只用现金导致累计收益失真
        current = values[-1] if values else (acct.total_assets or acct.cash or 0.0)
        cumulative_pnl = current - initial
        cumulative_pnl_pct = (cumulative_pnl / initial * 100.0) if initial else 0.0

        # 年化收益：基于首末快照的日历跨度（复合年化）
        annualized = 0.0
        if len(curve) >= 2 and initial > 0:
            try:
                d0 = datetime.strptime(curve[0]["date"], "%Y-%m-%d")
                d1 = datetime.strptime(curve[-1]["date"], "%Y-%m-%d")
                years = (d1 - d0).days / 365.25
                if years > 0:
                    annualized = ((current / initial) ** (1.0 / years) - 1.0) * 100.0
            except Exception:
                annualized = 0.0

        ts = self._trade_stats(account_id)
        return {
            "accountId": account_id,
            "initialCapital": round(initial, 2),
            "currentAssets": round(current, 2),
            "cumulativePnl": round(cumulative_pnl, 2),
            "cumulativePnlPct": round(cumulative_pnl_pct, 2),
            "totalReturn": round(cumulative_pnl_pct, 2),
            "annualizedReturn": round(annualized, 2),
            "maxDrawdown": self._max_drawdown(values),
            "sharpeRatio": self._sharpe(values),
            "winRate": ts["winRate"],
            "profitLossRatio": ts["profitLossRatio"],
            "tradeCount": ts["tradeCount"],
            "winCount": ts["winCount"],
            "lossCount": ts["lossCount"],
            "avgWin": ts["avgWin"],
            "avgLoss": ts["avgLoss"],
            "snapshotCount": len(curve),
        }

    def refresh_statistics(self, account_id: int) -> dict:
        """刷新：确保基线 + 今日快照存在，重算并写回账户绩效字段，返回统计。"""
        self.seed_baseline(account_id)
        self.take_snapshot(account_id)
        stats = self.get_statistics(account_id)
        AccountRepository().update_metrics(
            account_id,
            max_drawdown=stats["maxDrawdown"],
            sharpe_ratio=stats["sharpeRatio"],
            win_rate=stats["winRate"],
            profit_loss_ratio=stats["profitLossRatio"],
        )
        return stats
