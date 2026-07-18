"""模拟盘交易系统 — 资金与收益曲线 / 统计中心路由（M6）。

挂载前缀：/api/paper/stats
端点：
    POST /{account_id}/snapshot    当日权益快照（幂等 upsert）
    GET  /{account_id}/equity      收益曲线（?days= 可选，默认全量）
    GET  /{account_id}/statistics  统计指标（不写回）
    POST /{account_id}/refresh     重算并写回账户绩效字段（max_drawdown / sharpe_ratio / win_rate / profit_loss_ratio）
    POST /{account_id}/seed        注入建仓日基线快照（仅无快照账户）
"""
from fastapi import APIRouter, HTTPException, Query

from app.paper.schemas import EquityPoint, AccountStatistics
from app.paper.services.stats_service import StatsService
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperStats"])
_stats = StatsService()


@router.post("/{account_id}/snapshot", response_model=EquityPoint)
def take_snapshot(account_id: int, date: str = Query(None, description="快照日期 YYYY-MM-DD，默认今日")):
    """对账户做一次权益快照（默认今日，幂等 upsert）。"""
    try:
        snap = _stats.take_snapshot(account_id, date)
        return EquityPoint(
            date=snap.date, totalAssets=snap.total_assets, cash=snap.cash,
            positionValue=snap.position_value, dailyPnl=snap.daily_pnl,
            dailyPnlPct=snap.daily_pnl_pct, cumulativePnl=snap.cumulative_pnl,
            cumulativePnlPct=snap.cumulative_pnl_pct,
        )
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/equity", response_model=list[EquityPoint])
def equity_curve(account_id: int, days: int = Query(None, ge=1, le=2000, description="返回最近 N 个交易日")):
    """收益曲线（按日期升序的权益快照序列）。"""
    try:
        return [EquityPoint(**c) for c in _stats.get_equity_curve(account_id, days)]
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/statistics", response_model=AccountStatistics)
def statistics(account_id: int):
    """账户统计中心（由权益快照 + 平仓成交记录联合计算，不写回账户表）。"""
    try:
        return AccountStatistics(**_stats.get_statistics(account_id))
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/refresh", response_model=AccountStatistics)
def refresh(account_id: int):
    """刷新统计：确保基线 + 今日快照存在，重算并写回账户绩效字段，返回统计。"""
    try:
        return AccountStatistics(**_stats.refresh_statistics(account_id))
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/seed", response_model=EquityPoint)
def seed(account_id: int):
    """注入建仓日基线快照（初始资金）。仅当该账户无任何快照时有效。"""
    try:
        snap = _stats.seed_baseline(account_id)
        if snap is None:
            raise HTTPException(status_code=400, detail="该账户已存在快照，无需注入基线")
        return EquityPoint(
            date=snap.date, totalAssets=snap.total_assets, cash=snap.cash,
            positionValue=snap.position_value, dailyPnl=snap.daily_pnl,
            dailyPnlPct=snap.daily_pnl_pct, cumulativePnl=snap.cumulative_pnl,
            cumulativePnlPct=snap.cumulative_pnl_pct,
        )
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)
