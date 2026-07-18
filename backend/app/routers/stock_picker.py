"""AI 选股分析报告路由

POST /api/stock-picker/screen  —— 条件选股（A/港股/美股），返回 code+name
POST /api/stock-picker/analyze —— 选股逻辑分析（LLM，含规则兜底）
POST /api/stock-picker/report  —— 回测 + 成败归因
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional

from app.services import stock_picker_service as sps

router = APIRouter()

_MARKETS = ["a", "hk", "us"]


class ScreenRequest(BaseModel):
    market: str = Field("a", description="a / hk / us")
    expression: str = Field(..., description="westock-tool 选股表达式，如 intersect([PE_TTM > 0, PE_TTM < 15, ROETTM > 15])")
    limit: int = Field(20, ge=1, le=100)


class AnalyzeRequest(BaseModel):
    market: str = Field("a")
    expression: str = Field(...)
    candidates: List[dict] = Field(default_factory=list)


class ReportRequest(BaseModel):
    codes: List[str] = Field(..., min_length=1, max_length=50)
    strategy: str = Field("MA双均线交叉基准策略")
    startDate: str = Field("2024-01-01")
    endDate: str = Field("2026-07-10")
    stockPool: str = Field("沪深300")
    initialCapital: int = Field(1_000_000)


@router.post("/screen")
def post_screen(req: ScreenRequest):
    market = req.market if req.market in _MARKETS else "a"
    candidates = sps.screen(market, req.expression, req.limit)
    return {
        "market": market,
        "expression": req.expression,
        "count": len(candidates),
        "candidates": candidates,
    }


@router.post("/analyze")
def post_analyze(req: AnalyzeRequest):
    market = req.market if req.market in _MARKETS else "a"
    result = sps.analyze_logic(market, req.expression, req.candidates or [])
    return result


@router.post("/report")
def post_report(req: ReportRequest):
    backtests = sps.run_backtests(
        req.codes, req.strategy, req.startDate, req.endDate,
        pool=req.stockPool, capital=req.initialCapital,
    )
    agg = sps._aggregate(backtests)
    attr = sps.attribute(agg, backtests)
    return {
        "strategy": req.strategy,
        "startDate": req.startDate,
        "endDate": req.endDate,
        "backtests": backtests,
        "aggregate": agg,
        "attribution": attr,
    }
