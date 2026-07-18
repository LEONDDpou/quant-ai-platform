export interface AccountMetrics {
  totalAssets: number;
  todayPnl: number;
  todayPnlPct: number;
  totalPnl: number;
  totalPnlPct: number;
  annualizedReturn: number;
  maxDrawdown: number;
  winRate: number;
  availableCash: number;
  positionValue: number;
}

export interface MarketIndex {
  code: string;
  name: string;
  value: number;
  change: number;
  changePct: number;
  volume: string;
  sparkline: number[];
}

export interface Position {
  code: string;
  name: string;
  shares: number;
  costPrice: number;
  currentPrice: number;
  marketValue: number;
  pnl: number;
  pnlPct: number;
  weight: number;
  industry: string;
}

export interface Strategy {
  id: string;
  name: string;
  type: string;
  status: "running" | "stopped" | "backtesting";
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  description: string;
  equityCurve: { date: string; value: number }[];
  createdAt: string;
}

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  time: string;
  sentiment: "positive" | "negative" | "neutral";
  impact: number;
  relatedStocks: { code: string; name: string }[];
  summary: string;
}

export interface AIResearchReport {
  date: string;
  marketSummary: string;
  upReasons: string[];
  riskFactors: string[];
  focusStocks: { code: string; name: string; reason: string; risk: string }[];
  sentimentScore: number;
  aiJudgment: "bullish" | "neutral" | "bearish";
}

export interface StockAnalysis {
  code: string;
  name: string;
  fundamentalScore: number;
  technicalScore: number;
  capitalScore: number;
  sentimentScore: number;
  aiScore: number;
  klineData: KlineData[];
  indicators: {
    macd: { dif: number; dea: number; macd: number };
    kdj: { k: number; d: number; j: number };
    rsi: number;
    boll: { upper: number; mid: number; lower: number };
  };
  prediction: {
    d1: { direction: string; pct: number };
    d5: { direction: string; pct: number };
    d20: { direction: string; pct: number };
  };
}

export interface KlineData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

export interface BacktestResult {
  strategyName: string;
  startDate: string;
  endDate: string;
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  avgHoldDays: number;
  equityCurve: { date: string; value: number }[];
  trades: TradeRecord[];
}

export interface TradeRecord {
  date: string;
  code: string;
  name: string;
  action: "buy" | "sell";
  price: number;
  shares: number;
  amount: number;
  pnl?: number;
}
