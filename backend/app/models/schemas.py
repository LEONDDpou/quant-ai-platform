"""Pydantic 数据模型定义"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date


class AccountMetrics(BaseModel):
    totalAssets: float
    todayPnl: float
    todayPnlPct: float
    totalPnl: float
    totalPnlPct: float
    annualizedReturn: float
    maxDrawdown: float
    winRate: float
    availableCash: float
    positionValue: float


class MarketIndex(BaseModel):
    code: str
    name: str
    value: float
    change: float
    changePct: float
    volume: str
    sparkline: list[float]


class Position(BaseModel):
    code: str
    name: str
    shares: int
    costPrice: float
    currentPrice: float
    marketValue: float
    pnl: float
    pnlPct: float
    weight: float
    industry: str


class IndustryDist(BaseModel):
    name: str
    value: float
    color: str


class StrategyBase(BaseModel):
    id: str
    name: str
    type: str
    status: Literal["running", "stopped", "backtesting", "paused", "archived"]
    annualizedReturn: float
    sharpeRatio: float
    maxDrawdown: float
    winRate: float
    totalTrades: int
    description: str
    createdAt: str


class StrategyCreate(BaseModel):
    name: str
    type: str
    stockPool: str
    description: str


class NewsItem(BaseModel):
    id: str
    title: str
    source: str
    time: str
    sentiment: Literal["positive", "negative", "neutral"]
    impact: int
    relatedStocks: list[dict]
    summary: str


class AIResearchReport(BaseModel):
    date: str
    marketSummary: str
    upReasons: list[str]
    riskFactors: list[str]
    focusStocks: list[dict]
    sentimentScore: int
    aiJudgment: Literal["bullish", "neutral", "bearish"]
    outlook: str = ""


class AIResearcherReport(AIResearchReport):
    """AI 研究员每日报告（含 LLM 来源标识）。"""
    llmEnabled: bool = False
    model: str = ""
    generatedAt: str = ""


class StockAIAnalysis(BaseModel):
    code: str
    name: str
    summary: str = ""
    tags: list[str] = []
    rating: str = "中性"
    outlook: str = ""
    risk: str = ""
    llmEnabled: bool = False
    model: str = ""


class TradeOrder(BaseModel):
    code: str
    action: Literal["buy", "sell"]
    price: float
    shares: int


class BacktestConfig(BaseModel):
    strategy: str
    startDate: str
    endDate: str
    stockPool: str
    initialCapital: float
    code: Optional[str] = None  # 可选：指定回测标的（如 600519）


class DashboardResponse(BaseModel):
    account: AccountMetrics
    indices: list[MarketIndex]
    positions: list[Position]
    industryDist: list[IndustryDist]
    sentimentScore: int
    aiJudgment: str
    runningStrategies: int


# ── Phase 5: 策略优化器 ──

class OptimizeRequest(BaseModel):
    strategy: str = "MA双均线交叉基准策略"
    symbol: str = "sh000300"
    startDate: str = "2024-01-01"
    endDate: str = "2026-07-10"
    metric: Literal["sharpe", "total_return", "calmar"] = "sharpe"


class PortfolioBacktestRequest(BaseModel):
    strategies: list[str]
    symbols: list[str]
    startDate: str = "2024-01-01"
    endDate: str = "2026-07-10"
    initialCapital: float = 1_000_000
    weightScheme: Literal["equal", "sharpe_weighted", "inverse_volatility"] = "equal"


class StressTestRequest(BaseModel):
    symbol: str = "sh000300"
    initialCapital: float = 1_000_000
