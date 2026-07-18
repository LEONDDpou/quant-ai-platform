"""Stock API - 个股智能分析（接入 westock-data 真实行情 + 本地指标计算）"""
from fastapi import APIRouter, HTTPException
from app.services import data_provider as dp

router = APIRouter()


@router.get("/{code}/analysis")
def get_stock_analysis(code: str):
    """获取个股全景分析：行情 + K线 + 技术指标 + AI评分 + 预测"""
    try:
        return dp.get_stock_analysis(code)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"个股数据获取失败: {exc}")


@router.get("/{code}/kline")
def get_stock_kline(code: str, period: str = "day", limit: int = 120):
    """获取个股 K线数据"""
    try:
        return dp.get_stock_kline(code, period=period, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"K线数据获取失败: {exc}")
