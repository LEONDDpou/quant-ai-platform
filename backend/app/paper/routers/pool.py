"""模拟盘交易系统 — 股票池自动维护路由（M179）。

挂载前缀：/api/paper/pool
端点：
    GET  /sources                  可用同步源（行业/概念板块名，供前端下拉）
    GET  /{account_id}/items       股票池标的列表
    POST /{account_id}/items       新增标的（手动）
    PUT  /{account_id}/items/{id}  更新标的（分组/备注/锁定）
    DELETE /{account_id}/items/{id} 移除标的
    GET  /{account_id}/config      自动维护配置
    PUT  /{account_id}/config      新增/更新自动维护配置
    POST /{account_id}/maintain    立即执行一次自动维护
    GET  /{account_id}/changelog   变更日志
"""
from fastapi import APIRouter, HTTPException, Query

from app.paper.schemas import (
    PoolConfigRequest,
    PoolConfigResponse,
    PoolChangeLogResponse,
    PoolItemRequest,
    PoolItemResponse,
    PoolItemUpdateRequest,
    PoolMaintainResult,
)
from app.paper.services.pool_service import PoolMaintenanceService
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperPool"])
_pool = PoolMaintenanceService()


@router.get("/sources")
def list_sources():
    """可用同步源：行业/概念板块名称（真实源可用时补充市场实际板块）。"""
    try:
        return _pool.list_sources()
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/items", response_model=list[PoolItemResponse])
def list_pool_items(account_id: int):
    """股票池标的列表（含锁定/分组/健康状态）。"""
    try:
        return _pool.list_items(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/items", response_model=PoolItemResponse)
def add_pool_item(account_id: int, req: PoolItemRequest):
    """手动新增股票池标的。"""
    try:
        return _pool.add_item(account_id, req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.put("/{account_id}/items/{item_id}", response_model=PoolItemResponse)
def update_pool_item(account_id: int, item_id: int, req: PoolItemUpdateRequest):
    """更新标的（分组 / 备注 / 锁定开关）。"""
    try:
        return _pool.update_item(item_id, category=req.category, note=req.note, pinned=req.pinned)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/{account_id}/items/{item_id}")
def remove_pool_item(account_id: int, item_id: int):
    """移除股票池标的。"""
    try:
        return {"deleted": _pool.remove_item(item_id)}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/config", response_model=PoolConfigResponse)
def get_pool_config(account_id: int):
    """获取账户股票池自动维护配置（无记录返回默认）。"""
    try:
        return _pool.get_config(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.put("/{account_id}/config", response_model=PoolConfigResponse)
def upsert_pool_config(account_id: int, req: PoolConfigRequest):
    """新增或更新股票池自动维护配置。"""
    try:
        return _pool.upsert_config(account_id, req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/maintain", response_model=PoolMaintainResult)
def maintain_pool(account_id: int):
    """立即执行一次自动维护（同步成分 + 健康检测 + 按规则移除）。"""
    try:
        return _pool.run_maintenance(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/changelog", response_model=list[PoolChangeLogResponse])
def pool_changelog(account_id: int, limit: int = Query(100, ge=1, le=500)):
    """股票池变更日志（按时间倒序）。"""
    try:
        return _pool.get_changelog(account_id, limit=limit)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)
