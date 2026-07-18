"""AI 量化研究员路由 — 接 LLM 生成每日投资报告 / 个股深度解读。

- /api/ai-researcher/report  ：聚合真实指数/新闻/关注池 → LLM 生成结构化报告；
  未配置大模型或调用失败时，自动回退到规则合成（data_provider.get_ai_report），
  并通过 llmEnabled 字段明确告知前端来源。
- /api/ai-researcher/analyze  ：单只个股 LLM 深度解读，失败时回退规则合成摘要。
"""
import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import data_provider as dp
from app.services import llm_service as llm
from app.models.schemas import AIResearcherReport, StockAIAnalysis
from app.db import crud

router = APIRouter()


@router.get("/report", response_model=AIResearcherReport)
def get_report(refresh: bool = Query(False, description="true=绕过缓存重新生成")):
    """获取 AI 研究员每日投资报告（LLM 优先，规则合成兜底）。"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = llm.generate_report(refresh=refresh)
    if report:
        # 落库（失败不影响返回）
        crud.save_ai_report(report, True, llm.LLM_MODEL)
        return AIResearcherReport(
            **report,
            llmEnabled=True,
            model=llm.LLM_MODEL,
            generatedAt=now,
        )

    # 回退：规则合成
    rule = dp.get_ai_report()
    crud.save_ai_report(rule, False, "rule-based")
    return AIResearcherReport(
        **rule,
        llmEnabled=False,
        model="rule-based",
        generatedAt=now,
    )


@router.get("/history")
def get_report_history(limit: int = Query(20, ge=1, le=100)):
    """获取历史 AI 研究报告列表（持久化）。"""
    return crud.get_ai_report_history(limit) or []


@router.get("/analyze", response_model=StockAIAnalysis)
def get_stock_analysis_ai(code: str = Query(..., description="股票代码，如 600519")):
    """获取单只个股的 AI 深度解读（LLM 优先，规则合成兜底）。"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = llm.analyze_stock(code)
    if result:
        return StockAIAnalysis(**result, llmEnabled=True, model=llm.LLM_MODEL)

    # 回退：基于真实指标做轻量规则合成摘要
    try:
        a = dp.get_stock_analysis(code)
    except Exception:
        return StockAIAnalysis(code=code, name=code, llmEnabled=False, model="rule-based")

    rating = "看多" if a["aiScore"] >= 65 else ("看空" if a["aiScore"] <= 45 else "中性")
    summary = (
        f"{a['name']}（{a['code']}）最新价 {a['currentPrice']}，当日 {a['changePct']:+.2f}%。"
        f"综合 AI 评分 {a['aiScore']}/100（技术 {a['technicalScore']}、基本面 {a['fundamentalScore']}、"
        f"资金 {a['capitalScore']}、情绪 {a['sentimentScore']}）。"
        f"MACD {'红柱' if a['indicators']['macd']['macd'] > 0 else '绿柱'}，"
        f"RSI {a['indicators']['rsi']}。"
    )
    return StockAIAnalysis(
        code=a["code"],
        name=a["name"],
        summary=summary,
        tags=[f"AI{a['aiScore']}", f"RSI{a['indicators']['rsi']}"],
        rating=rating,
        outlook=f"短期方向：{a['prediction']['d5']['direction']}（约 {a['prediction']['d5']['pct']:.1f}%）",
        risk="技术指标为历史统计，不预示未来；请注意仓位与止损。",
        llmEnabled=False,
        model="rule-based",
    )
