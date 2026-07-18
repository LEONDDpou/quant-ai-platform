"""模拟盘交易系统 — 持仓接口。

挂载前缀（main.py 中 include_router）：/api/paper/position
"""
from fastapi import APIRouter, HTTPException

from app.paper.schemas import PositionResponse, PositionSummary
from app.paper.services.position_service import PositionService
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperPosition"])
_pos = PositionService()


@router.get("/{account_id}", response_model=list[PositionResponse])
def list_positions(account_id: int):
    """持仓列表（含市值/盈亏/可卖/T+1/仓位）。"""
    try:
        return _pos.list_positions(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/summary", response_model=PositionSummary)
def position_summary(account_id: int):
    """持仓汇总（M4）：市值/成本/浮动盈亏/已实现盈亏/当日盈亏/集中度/行业分布。"""
    try:
        return _pos.get_summary(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/refresh", response_model=list[PositionResponse])
def refresh_positions(account_id: int):
    """用实时行情刷新全部持仓市值/盈亏，返回刷新后的持仓列表。"""
    try:
        return _pos.refresh_market_value_public(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/rollover")
def rollover_day(account_id: int):
    """日终滚动：当日买入转可卖、持仓天数 +1（模拟 T+1 跨日）。"""
    try:
        _pos.rollover_day(account_id)
        return {"ok": True}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)
