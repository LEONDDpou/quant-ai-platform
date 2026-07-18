"""ABu ML 预测路由 — 暴露「数据驱动的 AI 涨跌预测」能力。

端点：
- POST /api/abu-ml/predict  ：body {code, horizon?} -> ABuML 预测结果
- GET  /api/abu-ml/predict  ：query ?code=600519&horizon=5

底层算法移植自开源项目 bbfamily/abu（abupy/MLBu + abupy/TradeBu/ABuMLFeature.py），
由 app.services.abu_ml_service 提供，喂入 westock 真实日 K 线。
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import abu_ml_service as abu_ml

router = APIRouter()


class AbuMLPredictRequest(BaseModel):
    code: str = Field(..., description="股票代码，如 600519 / 600519.SH / sh600519")
    horizon: int = Field(5, ge=1, le=60, description="预测未来 N 个交易日的方向")


class AbuMLFeatureImportance(BaseModel):
    feature: str
    importance: float


class AbuMLPredictResponse(BaseModel):
    code: str
    symbol: str
    horizon: int
    direction: str
    confidence: float
    testAccuracy: float
    testF1: float
    cvAccuracy: float
    nSamples: int
    featureImportance: list[AbuMLFeatureImportance]
    trainedAt: str
    note: str


@router.post("/predict", response_model=AbuMLPredictResponse)
@router.get("/predict", response_model=AbuMLPredictResponse)
def post_predict(
    req: AbuMLPredictRequest | None = None,
    code: str | None = Query(None, description="股票代码"),
    horizon: int = Query(5, ge=1, le=60),
):
    """ABu 风格 ML 涨跌方向预测（缓存 5 分钟）。"""
    if req is not None:
        code = req.code
        horizon = req.horizon
    if not code:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="缺少 code 参数")

    r = abu_ml.predict(code, horizon=horizon)
    return AbuMLPredictResponse(
        code=r.code,
        symbol=r.symbol,
        horizon=r.horizon,
        direction=r.direction,
        confidence=r.confidence,
        testAccuracy=r.test_accuracy,
        testF1=r.test_f1,
        cvAccuracy=r.cv_accuracy,
        nSamples=r.n_samples,
        featureImportance=[
            AbuMLFeatureImportance(feature=f["feature"], importance=f["importance"])
            for f in r.feature_importance
        ],
        trainedAt=r.trained_at,
        note=r.note,
    )
