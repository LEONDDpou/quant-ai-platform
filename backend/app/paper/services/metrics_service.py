"""模拟盘交易系统 — 账户指标计算。

M1 实现「可实时推导」的指标（总资产 / 持仓市值 / 可用资金 / 仓位比例 / 总盈亏 / 累计收益率）。
历史型指标（最大回撤 / 夏普 / 胜率 / 盈亏比 / 今日收益率）依赖日终快照与成交序列，
在 M6 收益曲线与统计中心落地后由快照驱动，M1 先读取账户表已存字段（默认 0）。
"""
from typing import List

from app.paper.domain_models import PaperAccount, PaperPosition


def compute_account_metrics(account: PaperAccount, positions: List[PaperPosition]) -> dict:
    position_value = sum((p.market_value or 0.0) for p in positions)
    total_assets = (account.cash or 0.0) + position_value
    initial = account.initial_capital or 0.0

    total_pnl = total_assets - initial
    total_pnl_pct = (total_pnl / initial * 100.0) if initial else 0.0
    position_ratio = (position_value / total_assets * 100.0) if total_assets else 0.0

    return {
        "totalAssets": total_assets,
        "positionValue": position_value,
        "availableCash": account.available_cash or 0.0,
        "positionRatio": position_ratio,
        "totalPnl": total_pnl,
        "totalPnlPct": total_pnl_pct,
        "todayPnl": account.today_pnl or 0.0,
        "todayPnlPct": ((account.today_pnl or 0.0) / (total_assets - (account.today_pnl or 0.0)) * 100.0)
                        if (total_assets - (account.today_pnl or 0.0)) else 0.0,
        "maxDrawdown": account.max_drawdown or 0.0,
        "sharpeRatio": account.sharpe_ratio or 0.0,
        "winRate": account.win_rate or 0.0,
        "profitLossRatio": account.profit_loss_ratio or 0.0,
    }
