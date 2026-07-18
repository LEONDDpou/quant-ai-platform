"""因子分析路由 — 暴露「QuantsPlaybook 风格因子评价」能力。

端点：
- POST /api/factor/analyze ：body {code, factor?, horizon?} -> 因子 IC/ICIR/分组收益
- GET  /api/factor/analyze ：query ?code=600519&factor=momentum&horizon=20

底层算法移植自开源项目 hugo2046/QuantsPlaybook（因子 Notebook + performance.py），
由 app.services.factor_service 提供，喂入 westock 真实日 K 线，仅依赖 scipy（不引 qlib/statsmodels）。
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import factor_service as fac

router = APIRouter()

_FACTORS = ["momentum", "reversal", "idio_vol", "ma_conv", "composite"]


class FactorGroup(BaseModel):
    group: int
    avgFactor: float
    avgForwardReturn: float
    count: int


class FactorAnalyzeRequest(BaseModel):
    code: str = Field(..., description="股票代码，如 600519 / 600519.SH / sh600519")
    factor: str = Field("momentum", description="因子: momentum/reversal/idio_vol/ma_conv/composite(多因子复合)")
    horizon: int = Field(20, ge=5, le=120, description="预测未来 N 个交易日的收益")


class FactorAnalyzeResponse(BaseModel):
    code: str
    symbol: str
    factor: str
    factorLabel: str
    horizon: int
    ic: float
    icir: float
    icWinRate: float
    longShortReturn: float
    groups: list[FactorGroup]
    latestFactor: float
    latestSignal: str
    nSamples: int
    startDate: str
    endDate: str
    note: str


@router.post("/analyze", response_model=FactorAnalyzeResponse)
@router.get("/analyze", response_model=FactorAnalyzeResponse)
def post_analyze(
    req: FactorAnalyzeRequest | None = None,
    code: str | None = Query(None, description="股票代码"),
    factor: str = Query("momentum", description="因子名"),
    horizon: int = Query(20, ge=5, le=120),
):
    """QuantsPlaybook 风格因子评价（IC / ICIR / 分组多空，缓存 5 分钟）。"""
    if req is not None:
        code = req.code
        factor = req.factor
        horizon = req.horizon
    if not code:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="缺少 code 参数")
    if factor not in _FACTORS:
        factor = "momentum"

    r = fac.analyze(code, factor=factor, horizon=horizon)
    return FactorAnalyzeResponse(
        code=r.code,
        symbol=r.symbol,
        factor=r.factor,
        factorLabel=r.factorLabel,
        horizon=r.horizon,
        ic=r.ic,
        icir=r.icir,
        icWinRate=r.icWinRate,
        longShortReturn=r.longShortReturn,
        groups=[FactorGroup(**g) for g in r.groups],
        latestFactor=r.latestFactor,
        latestSignal=r.latestSignal,
        nSamples=r.nSamples,
        startDate=r.startDate,
        endDate=r.endDate,
        note=r.note,
    )


# ============================================================
# 横截面因子研究（多股票 × 单因子）
# ============================================================
class CSGroup(BaseModel):
    group: int
    avgForwardReturn: float
    count: int


class CSPoint(BaseModel):
    date: str
    ic: float
    coverage: int


class CrossSectionRequest(BaseModel):
    index: str = Field("sh000300", description="指数代码，如 sh000300(沪深300) / sh000905(中证500)")
    factor: str = Field("momentum", description="因子: momentum/reversal/idio_vol/ma_conv/composite(多因子复合)")
    horizon: int = Field(20, ge=5, le=120, description="预测未来 N 个交易日的收益")
    sampleSize: int = Field(50, ge=10, le=300, description="从指数成份股中抽样的股票数量")


class CrossSectionResponse(BaseModel):
    factor: str
    factorLabel: str
    index: str
    horizon: int
    sampleSize: int
    nStocks: int
    nDates: int
    icMean: float
    icStd: float
    icir: float
    icWinRate: float
    longShortReturn: float
    icSeries: list[CSPoint]
    groups: list[CSGroup]
    startDate: str
    endDate: str
    note: str


@router.post("/cross-sectional", response_model=CrossSectionResponse)
def post_cross_sectional(req: CrossSectionRequest):
    """QuantsPlaybook 风格横截面因子研究：多股票抽样 × 单因子，计算逐日跨截面 IC 与五分组多空。"""
    if req.factor not in _FACTORS:
        factor = "momentum"
    else:
        factor = req.factor
    r = fac.cross_sectional_analyze(
        index=req.index, factor=factor, horizon=req.horizon, sample_size=req.sampleSize,
    )
    return CrossSectionResponse(
        factor=r.factor,
        factorLabel=r.factorLabel,
        index=r.index,
        horizon=r.horizon,
        sampleSize=r.sampleSize,
        nStocks=r.nStocks,
        nDates=r.nDates,
        icMean=r.icMean,
        icStd=r.icStd,
        icir=r.icir,
        icWinRate=r.icWinRate,
        longShortReturn=r.longShortReturn,
        icSeries=[CSPoint(**p) for p in r.icSeries],
        groups=[CSGroup(**g) for g in r.groups],
        startDate=r.startDate,
        endDate=r.endDate,
        note=r.note,
    )
