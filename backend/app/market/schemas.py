"""市场模块 API 响应模型（Pydantic）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class QuoteOut(BaseModel):
    code: str
    name: str = ""
    price: float = 0.0
    change: float = 0.0
    changePct: float = 0.0
    volume: int = 0
    amount: float = 0.0
    turnover: float = 0.0
    pe: float = 0.0
    pb: float = 0.0
    totalMv: float = 0.0
    floatMv: float = 0.0
    source: str = ""


class TechOut(BaseModel):
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    rsi14: Optional[float] = None
    macd: Optional[float] = None
    macdSignal: Optional[float] = None
    macdHist: Optional[float] = None


class CapitalFlowOut(BaseModel):
    code: str
    available: bool = True
    mainIn: float = 0.0
    ultraLarge: float = 0.0
    large: float = 0.0
    medium: float = 0.0
    small: float = 0.0
    mainNetFlow5d: float = 0.0


class AIScoreOut(BaseModel):
    score: float
    techScore: float = 0.0
    fundScore: float = 0.0
    sentimentScore: float = 0.0
    momentum: float = 0.0
    volatility: float = 0.0
    riskLevel: str = "low"


class RealtimeItem(BaseModel):
    quote: QuoteOut
    capitalFlow: Optional[CapitalFlowOut] = None
    technicals: TechOut = Field(default_factory=TechOut)
    aiScore: AIScoreOut


class RealtimeResponse(BaseModel):
    ts: str
    source: str
    count: int
    items: list[RealtimeItem]


class KlineBarOut(BaseModel):
    dt: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class BreadthOut(BaseModel):
    total: int = 0
    upCount: int = 0
    downCount: int = 0
    flatCount: int = 0
    limitUp: int = 0
    limitDown: int = 0
    breadthPct: float = 0.0


class SourceHealth(BaseModel):
    name: str
    available: bool
    circuit: str
    lastUsed: bool
