"""模拟盘交易系统 — 账户接口。

挂载前缀（在 main.py 中 include_router）：/api/paper/account
"""
from fastapi import APIRouter, HTTPException, Query

from app.paper.schemas import (
    CreateAccountRequest,
    AccountResponse,
    AccountMetricsResponse,
    AccountOverviewResponse,
    UpdateAccountRequest,
)
from app.paper.services.account_service import AccountService
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperAccount"])
_svc = AccountService()


@router.post("", response_model=AccountResponse)
def create_account(req: CreateAccountRequest):
    """创建模拟账户。"""
    try:
        return _svc.create_account(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("", response_model=list[AccountResponse])
def list_accounts(username: str = Query(None)):
    """模拟账户列表。"""
    try:
        return _svc.list_accounts(username)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


# ———— 静态路径（在动态 {account_id} 之前，避免 422 冲突） ————

@router.get("/overview", response_model=AccountOverviewResponse)
def account_overview(username: str = Query(None)):
    """全账户汇总统计。"""
    return _svc.get_overview(username)


# ———— 动态路径（含 {account_id} 参数） ————

@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: int):
    """账户详情（含实时指标）。"""
    try:
        return _svc.get_account(account_id)
    except PaperError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get("/{account_id}/metrics", response_model=AccountMetricsResponse)
def get_account_metrics(account_id: int):
    """账户指标。"""
    try:
        return _svc.get_metrics(account_id)
    except PaperError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.put("/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, req: UpdateAccountRequest):
    """更新账户（名称/初始资金）。"""
    try:
        return _svc.update_account(account_id, req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/{account_id}")
def delete_account(account_id: int):
    """删除账户及关联数据。"""
    try:
        ok = _svc.delete_account(account_id)
        return {"deleted": ok}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)
