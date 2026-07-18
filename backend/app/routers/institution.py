"""机构维度聚合 API — 统一入口，减少分析工具重复查询"""
from fastapi import APIRouter

from app.services import institution_aggregation as ia

router = APIRouter()


@router.get("/aggregate")
def get_institution_aggregate():
    """获取机构维度完整聚合数据：龙虎榜 + 资金流向 + 北向 + 持仓偏好 + 活跃度。"""
    return ia.get_institution_aggregate()


@router.get("/activity")
def get_activity():
    """获取机构交易活跃度指标。"""
    return ia.get_institution_activity()


@router.get("/positions")
def get_positions():
    """获取机构持仓特征（重仓行业 + 净买入个股）。"""
    return ia.get_institution_positions()


@router.get("/northbound")
def get_northbound():
    """获取北向资金净流入。"""
    return ia.get_northbound_flow()
