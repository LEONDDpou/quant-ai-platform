"""研究员 Agent 路由（#182）。

端点（前缀 /api/paper/research）：
- POST /run                ：触发一次研究员研究（挖因子 + 生成策略）
- GET  /sessions           ：列举研究会话（按账户；accountId 缺省含全局）
- GET  /sessions/{id}      ：会话详情（含因子结论 + 策略想法）
- GET  /ideas              ：列举策略想法
- GET  /ideas/{id}         ：策略想法详情
- POST /ideas/{id}/backtest：对该想法触发事件驱动回测（贯通 M181）
- DELETE /ideas/{id}       ：删除策略想法
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.paper.errors import PaperError
from app.paper.schemas import (
    PaperResearchSessionResponse,
    PaperStrategyIdeaResponse,
    RunResearchRequest,
    RunResearchResponse,
)
from app.paper.services.research_service import ResearcherAgentService

router = APIRouter(tags=["PaperResearch"])
_research = ResearcherAgentService()


@router.post("/run", response_model=RunResearchResponse)
def run_research(req: RunResearchRequest):
    """触发一次研究员 Agent 研究：因子挖掘 + 策略生成并落库。"""
    try:
        return _research.run_research(req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions", response_model=list[PaperResearchSessionResponse])
def list_sessions(account_id: Optional[int] = Query(None, description="账户ID；缺省含全局会话")):
    """列举研究会话。"""
    return _research.list_sessions(account_id)


@router.get("/sessions/{session_id}", response_model=PaperResearchSessionResponse)
def get_session(session_id: int):
    """研究会话详情（含因子结论与策略想法）。"""
    try:
        return _research.get_session(session_id)
    except PaperError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/ideas", response_model=list[PaperStrategyIdeaResponse])
def list_ideas(account_id: Optional[int] = Query(None, description="账户ID；缺省含全局想法")):
    """列举策略想法。"""
    return _research.list_ideas(account_id)


@router.get("/ideas/{idea_id}", response_model=PaperStrategyIdeaResponse)
def get_idea(idea_id: int):
    """策略想法详情。"""
    try:
        return _research.get_idea(idea_id)
    except PaperError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/ideas/{idea_id}/backtest", response_model=dict)
def backtest_idea(idea_id: int, account_id: Optional[int] = Query(None)):
    """对该策略想法触发事件驱动回测，并返回回测结果（贯通 M181）。"""
    try:
        resp = _research.backtest_idea(idea_id, account_id)
        return {"runId": resp.id, "mode": resp.mode, "totalReturn": resp.totalReturn,
                "sharpeRatio": resp.sharpeRatio, "maxDrawdown": resp.maxDrawdown,
                "winRate": resp.winRate, "totalTrades": resp.totalTrades}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/ideas/{idea_id}")
def delete_idea(idea_id: int):
    """删除策略想法。"""
    deleted = _research.delete_idea(idea_id)
    return {"deleted": deleted}
