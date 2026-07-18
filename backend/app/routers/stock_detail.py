"""Stock Detail Router — 个股详情聚合接口"""
from fastapi import APIRouter, Query, HTTPException

from app.services.stock_detail_service import get_stock_detail

router = APIRouter()


@router.get("/{code}")
def stock_detail(
    code: str,
    force: bool = Query(False, description="跳过缓存强制刷新"),
):
    """获取个股完整详情（公司资料 + 三张报表 + 新闻 + 实时动态）。

    示例:
        GET /api/stock-detail/sz300043
        GET /api/stock-detail/sh600519
        GET /api/stock-detail/hk00700?force=true
    """
    try:
        detail = get_stock_detail(code, force=force)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not detail.get("profile"):
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的资料")

    return detail
