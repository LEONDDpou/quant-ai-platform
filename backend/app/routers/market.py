"""Market API - 市场行情数据（接入 westock-data 真实行情）"""
from fastapi import APIRouter, HTTPException
from app.services import data_provider as dp

router = APIRouter()


@router.get("/indices")
def get_indices():
    """获取主要指数实时行情"""
    return dp.get_indices()


@router.get("/indices/{code}")
def get_index(code: str):
    """获取单个指数详情"""
    for idx in dp.get_indices():
        if idx["code"] == code:
            return idx
    raise HTTPException(status_code=404, detail="Index not found")
