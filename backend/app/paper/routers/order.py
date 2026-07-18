"""模拟盘交易系统 — 订单与持仓接口。

挂载前缀（main.py 中 include_router）：/api/paper/order
持仓接口挂载：/api/paper/position
"""
from fastapi import APIRouter, HTTPException, Query

from app.paper.schemas import (
    CreateOrderRequest,
    OrderResponse,
)
from app.paper.services.order_service import OrderService
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperOrder"])
_svc = OrderService()


@router.post("", response_model=list[OrderResponse])
def create_order(req: CreateOrderRequest):
    """创建订单（限价/市价/止盈/止损/网格/分批/AI）。分批或网格返回多笔。"""
    try:
        return _svc.create_order(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}", response_model=list[OrderResponse])
def list_orders(account_id: int, status: str = Query(None), orderType: str = Query(None)):
    """订单列表（可按状态/类型过滤）。"""
    try:
        return _svc.list_orders(account_id, status)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/{order_id}", response_model=OrderResponse)
def get_order(account_id: int, order_id: int):
    """订单详情。"""
    try:
        return _svc.get_order(account_id, order_id)
    except PaperError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.post("/{account_id}/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(account_id: int, order_id: int):
    """撤单。"""
    try:
        return _svc.cancel_order(account_id, order_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/match")
def retry_match(account_id: int = Query(None)):
    """手动触发挂单重试撮合（后台也会定时执行）。"""
    try:
        n = _svc.retry_pending_orders(account_id)
        return {"matched": n}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)
