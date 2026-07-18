"""组合管理 API — 模拟账户 + Brinson 归因 + VaR/CVaR + 再平衡。

端点：
  GET  /overview      — 账户概览（总资产/现金/持仓市值/当日盈亏）
  GET  /positions     — 当前持仓列表
  GET  /attribution   — Brinson 收益归因
  GET  /risk           — 风险指标（VaR/CVaR/波动率/夏普/最大回撤）
  GET  /rebalance     — 再平衡建议
  POST /order         — 模拟下单
  GET  /orders        — 订单历史
  DELETE /order/{id}  — 撤单
  POST /snapshot      — 保存当天快照
  GET  /snapshots     — 历史快照序列
  GET  /full          — 全量数据（概览+持仓+风险）
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import portfolio_service as ps

router = APIRouter()


class OrderRequest(BaseModel):
    code: str
    name: str = ""
    direction: str           # buy / sell
    shares: int
    price: float | None = None
    reason: str = ""


class TargetWeightsRequest(BaseModel):
    target_weights: dict | None = None


# ── 账户概览 ──
@router.get("/overview")
def overview():
    """获取账户概览：总资产 / 现金 / 持仓市值 / 当日盈亏。"""
    return ps.get_account_summary()


# ── 持仓 ──
@router.get("/positions")
def positions():
    """获取当前持仓列表（实时估值）。"""
    return ps.get_positions()


# ── Brinson 归因 ──
@router.get("/attribution")
def attribution():
    """Brinson 收益归因：配置效应 + 选股效应 + 交互效应。"""
    return ps.get_attribution()


# ── 风险指标 ──
@router.get("/risk")
def risk(confidence: float = Query(0.95, ge=0.90, le=0.99)):
    """历史模拟法 VaR / CVaR / 年化波动率 / 夏普比率 / 最大回撤。"""
    return ps.get_risk_metrics(confidence)


# ── 再平衡建议 ──
@router.get("/rebalance")
def rebalance():
    """再平衡建议：当前行业权重 vs 目标权重偏离度 + 调仓方案。"""
    return ps.get_rebalance_advice()


@router.post("/rebalance")
def rebalance_with_targets(req: TargetWeightsRequest):
    """使用自定义目标权重生成再平衡建议。"""
    return ps.get_rebalance_advice(req.target_weights)


# ── 下单 ──
@router.post("/order")
def place_order(req: OrderRequest):
    """模拟下单：code + direction + shares + price(可选)，自动成交。"""
    if req.direction not in ("buy", "sell"):
        return {"error": "方向必须为 buy 或 sell", "status": "failed"}
    return ps.place_order(
        code=req.code,
        name=req.name,
        direction=req.direction,
        shares=req.shares,
        price=req.price,
        reason=req.reason,
    )


# ── 订单历史 ──
@router.get("/orders")
def orders(limit: int = Query(50, ge=5, le=200)):
    """获取历史订单列表（最近 N 条）。"""
    return ps.get_orders(limit)


# ── 撤单 ──
@router.delete("/order/{order_id}")
def cancel_order(order_id: int):
    """撤单（仅限 pending 状态订单）。"""
    return ps.cancel_order(order_id)


# ── 快照 ──
@router.post("/snapshot")
def take_snapshot():
    """保存当前组合快照。"""
    return ps.take_snapshot()


@router.get("/snapshots")
def snapshots(days: int = Query(30, ge=1, le=365)):
    """获取历史快照序列。"""
    return ps.get_snapshot_history(days)


# ── 全量数据 ──
@router.get("/full")
def full():
    """组合全量数据：概览 + 持仓 + 风险。"""
    return ps.get_portfolio_full()
