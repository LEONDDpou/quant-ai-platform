"""市场温度 API — 温度查询、历史曲线、四维拆解。"""
from fastapi import APIRouter, Query

from app.services import market_temperature_service as mts

router = APIRouter()


@router.get("")
def get_temperature(force: bool = Query(False, description="强制刷新，跳过缓存")):
    """获取当前市场温度（四维拆解 + 综合评分 0-100）。"""
    return mts.get_market_temperature(force=force)


@router.get("/history")
def get_history(days: int = Query(30, ge=7, le=365, description="查询天数")):
    """获取历史温度时间序列。"""
    return {
        "temperature": mts.get_temperature_history(days),
        "days": days,
    }
