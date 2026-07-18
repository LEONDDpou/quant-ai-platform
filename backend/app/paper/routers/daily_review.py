"""AI 每日复盘报告路由（#186）。

端点（前缀 /api/paper/daily-review）：
- GET   /{account_id}/latest     ：最新复盘
- GET   /{account_id}/list       ：复盘历史
- POST  /{account_id}/generate   ：手动触发生成
"""
from fastapi import APIRouter, HTTPException, Query

from app.paper.errors import PaperError
from app.paper.schemas import DailyReviewResponse
from app.paper.services.daily_review_service import DailyReviewService

router = APIRouter(tags=["PaperDailyReview"])
_svc = DailyReviewService()


@router.get("/{account_id}/latest", response_model=DailyReviewResponse)
def get_latest_review(account_id: int):
    latest = _svc.get_latest(account_id)
    if not latest:
        raise HTTPException(status_code=404, detail="暂无复盘")
    return latest


@router.get("/{account_id}/list", response_model=list[DailyReviewResponse])
def list_reviews(account_id: int, limit: int = Query(20)):
    return _svc.list_reviews(account_id, limit)


@router.post("/{account_id}/generate", response_model=DailyReviewResponse)
def generate_review(account_id: int):
    try:
        return _svc.generate_review(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=str(e))
