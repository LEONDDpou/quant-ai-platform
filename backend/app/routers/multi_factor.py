"""多因子评分 API — 五维因子模型 + 截面排名 + IC 分析。

端点：
- GET  /api/multi-factor/score?code=sh600519              → 单股评分
- POST /api/multi-factor/batch   {codes:[...]}            → 批量评分
- GET  /api/multi-factor/ranking                           → 排名（综合/单维度）
- GET  /api/multi-factor/ic-analysis                       → 因子截面 IC 分析
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import multi_factor_service as mf

router = APIRouter()


# ===== 请求/响应模型 =====
class SubFactorItem(BaseModel):
    label: str = ""
    score: float = 0.0


class DimensionItem(BaseModel):
    score: float = 0.0
    label: str = ""
    subFactors: dict[str, float] = {}


class FactorScoreResponse(BaseModel):
    code: str
    name: str
    industry: str
    totalScore: float
    percentile: float
    rank: int
    universeSize: int
    dimensions: dict[str, dict]   # {value: {score, label, subFactors}, ...}
    dataTimestamp: str
    note: str


class BatchScoreRequest(BaseModel):
    codes: list[str] = Field(..., min_length=1, max_length=200, description="股票代码列表，如 ['sh600519', 'sz000858']")


class BatchScoreResponse(BaseModel):
    results: list[FactorScoreResponse]
    universeSize: int
    topCodes: list[str] = []
    dataTimestamp: str = ""


class FactorICItem(BaseModel):
    ic: float
    pValue: float
    label: str
    significant: bool


class ICAnalysisResponse(BaseModel):
    factors: dict[str, FactorICItem]
    sampleSize: int
    note: str


# ===== 端点 =====
@router.get("/score", response_model=FactorScoreResponse)
def get_score(code: str = Query(..., description="股票代码，如 sh600519 / 600519.SH / 600519")):
    """获取单只股票的多因子综合评分（五维拆解 + 截面百分位）。"""
    r = mf.score_stock(code)
    return FactorScoreResponse(
        code=r.code, name=r.name, industry=r.industry,
        totalScore=r.totalScore, percentile=r.percentile,
        rank=r.rank, universeSize=r.universeSize,
        dimensions=r.dimensions, dataTimestamp=r.dataTimestamp, note=r.note,
    )


@router.post("/batch", response_model=BatchScoreResponse)
def post_batch(req: BatchScoreRequest):
    """批量多因子评分（自动构建截面并百分位排名）。"""
    results = mf.batch_score(req.codes)
    if not results:
        return BatchScoreResponse(results=[], universeSize=0, topCodes=[],
                                  dataTimestamp="")
    items = [
        FactorScoreResponse(
            code=r.code, name=r.name, industry=r.industry,
            totalScore=r.totalScore, percentile=r.percentile,
            rank=r.rank, universeSize=r.universeSize,
            dimensions=r.dimensions, dataTimestamp=r.dataTimestamp, note=r.note,
        )
        for r in results
    ]
    top3 = [r.code for r in results[:3]] if results else []
    return BatchScoreResponse(
        results=items, universeSize=len(results), topCodes=top3,
        dataTimestamp=items[0].dataTimestamp if items else "",
    )


@router.get("/ranking", response_model=BatchScoreResponse)
def get_ranking(
    dimension: str | None = Query(None, description="按某维度排名: value/quality/momentum/volatility/sentiment"),
    limit: int = Query(20, ge=5, le=100),
):
    """获取因子排名列表（全市场截面，可选按单维度排序）。"""
    if dimension and dimension not in mf.FACTOR_LABELS_ZH:
        dimension = None
    results = mf.ranking(dimension=dimension, limit=limit)
    items = [
        FactorScoreResponse(
            code=r.code, name=r.name, industry=r.industry,
            totalScore=r.totalScore, percentile=r.percentile,
            rank=r.rank, universeSize=r.universeSize,
            dimensions=r.dimensions, dataTimestamp=r.dataTimestamp, note=r.note,
        )
        for r in results
    ]
    top3 = [r.code for r in results[:3]] if results else []
    return BatchScoreResponse(
        results=items, universeSize=len(results), topCodes=top3,
        dataTimestamp=items[0].dataTimestamp if items else "",
    )


@router.get("/ic-analysis", response_model=ICAnalysisResponse)
def get_ic_analysis():
    """因子截面 IC 分析：各维度得分与历史收益的秩相关。"""
    r = mf.ic_analysis()
    items = {}
    for dim_key, dim_data in r.get("factors", {}).items():
        items[dim_key] = FactorICItem(
            ic=dim_data["ic"],
            pValue=dim_data["pValue"],
            label=dim_data["label"],
            significant=dim_data["significant"],
        )
    return ICAnalysisResponse(
        factors=items,
        sampleSize=r.get("sampleSize", 0),
        note=r.get("note", ""),
    )
