"""News API - 新闻与市场情绪（接入 westock-data 真实新闻）"""
from fastapi import APIRouter, Query
from app.services import data_provider as dp
from app.db import crud

router = APIRouter()


@router.get("/")
def list_news(cache: bool = Query(True, description="true=拉取后写入数据库缓存")):
    """获取沪深市场实时新闻（并落库去重缓存）"""
    items = dp.get_news()
    if cache:
        crud.upsert_news_items(items)
    return items


@router.get("/history")
def news_history(limit: int = Query(50, ge=1, le=200)):
    """获取历史新闻（持久化缓存）。"""
    return crud.get_news_history(limit) or []


@router.get("/sentiment")
def get_sentiment():
    """获取市场情绪指数（基于真实指数 + 新闻合成）"""
    news = dp.get_news()
    report = dp.get_ai_report()
    positive = sum(1 for n in news if n["sentiment"] == "positive")
    negative = sum(1 for n in news if n["sentiment"] == "negative")
    neutral = sum(1 for n in news if n["sentiment"] == "neutral")
    return {
        "score": report["sentimentScore"],
        "judgment": report["aiJudgment"],
        "distribution": {"positive": positive, "negative": negative, "neutral": neutral},
    }


@router.get("/ai-report")
def get_ai_report():
    """获取AI研究报告（基于真实行情合成）"""
    return dp.get_ai_report()
