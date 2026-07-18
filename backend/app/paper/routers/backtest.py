"""模拟盘交易系统 — M8 回测路由。

挂载前缀：/api/paper/backtest
端点：
    POST /run                      运行一次回测（落库 + 导出产物）
    GET  /runs                     回测历史列表（?account_id=&limit=）
    GET  /runs/{run_id}            回测详情
    GET  /strategies               可选策略列表（前端下拉）
    GET  /runs/{run_id}/file/{filename}  下载产物（index.html/equity.csv/trades.csv/summary.json）
"""
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Path as FPath
from fastapi.responses import FileResponse

from app.paper.schemas import (
    RunBacktestRequest,
    RunEventBacktestRequest,
    BacktestRunResponse,
    BacktestStrategyOption,
    BacktestEventStrategy,
)
from app.paper.services.backtest_service import BacktestService, BACKTEST_RESULTS_DIR
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperBacktest"])
_bt = BacktestService()

_ALLOWED_FILES = {"index.html", "equity.csv", "trades.csv", "summary.json"}


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(req: RunBacktestRequest):
    """运行一次回测（基于主平台回测引擎，严格防未来函数）。"""
    try:
        return _bt.run(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/runs", response_model=list[BacktestRunResponse])
def list_runs(
    account_id: int = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """回测历史列表（account_id 为空返回全部账户）。"""
    try:
        return _bt.list_runs(account_id=account_id, limit=limit)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/runs/{run_id}", response_model=BacktestRunResponse)
def get_run(run_id: int):
    """回测详情。"""
    try:
        return _bt.get(run_id)
    except PaperError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get("/strategies", response_model=list[BacktestStrategyOption])
def strategies():
    """可选策略列表（供前端下拉）。"""
    return _bt.strategy_options()


@router.get("/event-strategies", response_model=list[BacktestEventStrategy])
def event_strategies():
    """事件驱动策略模板列表（供前端下拉 + 规则预设）。"""
    return _bt.event_strategy_templates()


@router.post("/event-backtest", response_model=BacktestRunResponse)
def run_event_backtest(req: RunEventBacktestRequest):
    """运行一次事件驱动回测（多标的等权组合，严格防未来函数）。"""
    try:
        return _bt.run_event(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/runs/{run_id}/file/{filename}")
def download_file(
    run_id: int,
    filename: str = FPath(..., description="index.html / equity.csv / trades.csv / summary.json"),
):
    """下载回测产物（三标准文件 + HTML 仪表盘）。"""
    if filename not in _ALLOWED_FILES:
        raise HTTPException(status_code=400, detail="不允许下载该文件")
    # 防御路径穿越：仅允许访问该 run 目录下的白名单文件
    target = (BACKTEST_RESULTS_DIR / str(run_id) / filename).resolve()
    base = (BACKTEST_RESULTS_DIR / str(run_id)).resolve()
    if not str(target).startswith(str(base) + os.sep) or not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    media = {
        "index.html": "text/html; charset=utf-8",
        "equity.csv": "text/csv; charset=utf-8",
        "trades.csv": "text/csv; charset=utf-8",
        "summary.json": "application/json; charset=utf-8",
    }.get(filename, "application/octet-stream")
    return FileResponse(str(target), media_type=media, filename=filename)
