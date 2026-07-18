"""模拟盘交易系统 — M7 AI 自动交易路由。

挂载前缀：/api/paper/auto
端点：
    GET  /{account_id}/strategies        策略列表
    POST /{account_id}/strategies        创建/更新策略
    POST /{account_id}/strategies/{strategy_id}/toggle  启停策略
    POST /{account_id}/run               运行一轮（手动触发）
    GET  /{account_id}/signals           信号列表
    GET  /{account_id}/logs              AI 日志
    GET  /{account_id}/status            运行状态
    POST /{account_id}/holdings/sltp     设置持仓止损/止盈
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Body

from app.paper.schemas import (
    PaperStrategyConfig,
    PaperSignal,
    PaperAILog,
    PaperAutoStatus,
    PaperHoldingSLTP,
)
from app.paper.services.auto_trade_service import AutoTradeService
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperAuto"])
_auto = AutoTradeService()


@router.get("/{account_id}/strategies", response_model=List[PaperStrategyConfig])
def list_strategies(account_id: int):
    try:
        out = []
        for s in _auto.list_strategies(account_id):
            out.append(PaperStrategyConfig(
                id=s.id, accountId=s.account_id, name=s.name,
                description=s.description or "", enabled=bool(s.enabled),
                params=s.params or {}, metrics=s.metrics or {},
                createdAt=s.created_at.isoformat() if s.created_at else "",
                updatedAt=s.updated_at.isoformat() if s.updated_at else "",
            ))
        return out
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/strategies", response_model=PaperStrategyConfig)
def create_or_update_strategy(account_id: int, body: dict = Body(...)):
    try:
        s = _auto.create_or_update_strategy(account_id, body)
        return PaperStrategyConfig(
            id=s.id, accountId=s.account_id, name=s.name,
            description=s.description or "", enabled=bool(s.enabled),
            params=s.params or {}, metrics=s.metrics or {},
            createdAt=s.created_at.isoformat() if s.created_at else "",
            updatedAt=s.updated_at.isoformat() if s.updated_at else "",
        )
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/strategies/{strategy_id}/toggle", response_model=PaperStrategyConfig)
def toggle_strategy(account_id: int, strategy_id: str, enabled: bool = Body(..., embed=True)):
    try:
        s = _auto.set_enabled(account_id, strategy_id, enabled)
        return PaperStrategyConfig(
            id=s.id, accountId=s.account_id, name=s.name,
            description=s.description or "", enabled=bool(s.enabled),
            params=s.params or {}, metrics=s.metrics or {},
            createdAt=s.created_at.isoformat() if s.created_at else "",
            updatedAt=s.updated_at.isoformat() if s.updated_at else "",
        )
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/run")
def run_once(account_id: int, strategy_id: Optional[str] = Query(None)):
    """手动触发一轮 AI 自动交易（与后台循环共用同一引擎）。"""
    try:
        return _auto.run_once(account_id, strategy_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/signals", response_model=List[PaperSignal])
def list_signals(account_id: int, limit: int = Query(50, ge=1, le=500),
                 code: Optional[str] = Query(None)):
    try:
        out = []
        for s in _auto.list_signals(account_id, limit=limit, code=code):
            out.append(PaperSignal(
                id=s.id, accountId=s.account_id, code=s.code, name=s.name,
                signalType=s.signal_type, strength=s.strength, source=s.source,
                reason=s.reason or "", priceTarget=s.price_target,
                stopLoss=s.stop_loss, takeProfit=s.take_profit,
                riskScore=s.risk_score,
                createdAt=s.created_at.isoformat() if s.created_at else "",
            ))
        return out
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/logs", response_model=List[PaperAILog])
def list_logs(account_id: int, limit: int = Query(50, ge=1, le=500)):
    try:
        out = []
        for l in _auto.list_ai_logs(account_id, limit=limit):
            out.append(PaperAILog(
                id=l.id, accountId=l.account_id, logType=l.log_type,
                level=l.level, message=l.message, meta=l.meta or {},
                createdAt=l.created_at.isoformat() if l.created_at else "",
            ))
        return out
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/status", response_model=PaperAutoStatus)
def auto_status(account_id: int):
    try:
        return PaperAutoStatus(**_auto.auto_status(account_id))
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/holdings/sltp", response_model=PaperHoldingSLTP)
def set_holding_sltp(account_id: int, body: dict = Body(...)):
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="缺少 code")
    sl = float(body.get("stopLossPrice", 0.0) or 0.0)
    tp = float(body.get("takeProfitPrice", 0.0) or 0.0)
    try:
        pos = _auto.set_holding_sltp(account_id, code, sl, tp)
        return PaperHoldingSLTP(
            accountId=pos.account_id, code=pos.code, name=pos.name,
            shares=pos.shares, costPrice=pos.cost_price,
            currentPrice=pos.current_price,
            stopLossPrice=pos.stop_loss_price,
            takeProfitPrice=pos.take_profit_price, pnlPct=pos.pnl_pct,
        )
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)
