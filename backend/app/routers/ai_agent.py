"""AI Agent API — 多 Agent 协作市场研判 + 行业分析 + 策略建议。"""
from fastapi import APIRouter, Query

from app.services import ai_agent_service as aas

router = APIRouter()


@router.post("/market-judgment")
def market_judgment(force: bool = Query(False, description="强制刷新")):
    """多 Agent 协作生成今日市场综合研判（大盘判断 + 风险星级 + 机会板块 + 操作建议 + AI评分）。"""
    return aas.generate_market_judgment(force=force)


@router.post("/sector-analysis")
def sector_analysis(topic: str = Query("", description="分析主题（可选）")):
    """行业板块 AI 分析（看好的板块/看空的板块/当前主题/展望）。"""
    return aas.analyze_sector(topic=topic)
