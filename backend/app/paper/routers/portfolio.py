"""策略组合管理路由（#184）。

端点（前缀 /api/paper/portfolio）：
- GET   /                      ：列表（按 account_id）
- POST  /                      ：创建
- GET   /{id}                  ：详情
- PUT   /{id}                  ：更新
- DELETE /{id}                 ：删除
- POST  /{id}/run              ：运行组合中所有策略
- POST  /{id}/rebalance        ：再平衡（更新分配+运行）
- GET   /{id}/rebalances       ：再平衡历史
"""
from fastapi import APIRouter, HTTPException, Query

from app.paper.errors import PaperError
from app.paper.schemas import (
    PortfolioRebalanceResponse,
    PortfolioRequest,
    PortfolioResponse,
)
from app.paper.services.portfolio_service import PortfolioService

router = APIRouter(tags=["PaperPortfolio"])
_ps = PortfolioService()


@router.get("", response_model=list[PortfolioResponse])
def list_portfolios(account_id: int = Query(...)):
    return _ps.list_portfolios(account_id)


@router.post("", response_model=PortfolioResponse)
def create_portfolio(req: PortfolioRequest):
    try:
        return _ps.create_portfolio(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(portfolio_id: int):
    obj = _ps.get_portfolio(portfolio_id)
    if not obj:
        raise HTTPException(status_code=404, detail="组合不存在")
    return obj


@router.put("/{portfolio_id}", response_model=PortfolioResponse)
def update_portfolio(portfolio_id: int, req: PortfolioRequest):
    try:
        return _ps.update_portfolio(portfolio_id, req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: int):
    ok = _ps.delete_portfolio(portfolio_id)
    return {"deleted": ok}


@router.post("/{portfolio_id}/run")
def run_portfolio(portfolio_id: int):
    try:
        return _ps.run_portfolio(portfolio_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{portfolio_id}/rebalance", response_model=PortfolioRebalanceResponse)
def rebalance_portfolio(portfolio_id: int, req: PortfolioRequest, reason: str = Query("")):
    try:
        return _ps.rebalance(portfolio_id, req, reason)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{portfolio_id}/rebalances", response_model=list[PortfolioRebalanceResponse])
def list_rebalances(portfolio_id: int, limit: int = Query(20)):
    return _ps.list_rebalances(portfolio_id, limit)
