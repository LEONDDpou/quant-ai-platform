// 后端 API 请求层 — 统一封装，前端各页面从此处获取（真实）数据
// 后端基地址统一从 ./config 引入，避免各地写死 localhost。

import { API_BASE } from "./config";

async function extractError(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  if (!text) return `${res.status}`;
  try {
    const j = JSON.parse(text);
    if (j && typeof j.detail === "string") return j.detail;
    if (j && typeof j.message === "string") return j.message;
  } catch {
    /* 非 JSON，原文返回 */
  }
  return text;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractError(res));
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await extractError(res));
  return res.json() as Promise<T>;
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await extractError(res));
  return res.json() as Promise<T>;
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await extractError(res));
  return res.json() as Promise<T>;
}

// ============ Dashboard ============
export interface DashboardData {
  account: {
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
  };
  indices: {
    code: string;
    name: string;
    value: number;
    change: number;
    changePct: number;
    volume: string;
    sparkline: number[];
  }[];
  positions: unknown[];
  industryDist: { name: string; value: number; color: string }[];
  sentimentScore: number;
  aiJudgment: string;
  runningStrategies: number;
  runningStrategyList?: { id: string; name: string; annualizedReturn: number; sharpeRatio: number }[];
  equityCurve: { date: string; value: number }[];
  dataSource?: string;
}

export const fetchDashboard = () => get<DashboardData>("/api/dashboard/");

// ============ Market ============
export const fetchIndices = () =>
  get<
    {
      code: string;
      name: string;
      value: number;
      change: number;
      changePct: number;
      volume: string;
      sparkline: number[];
    }[]
  >("/api/market/indices");

// ============ News ============
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

export const fetchNews = () => get<NewsItem[]>("/api/news/");
export const fetchSentiment = () =>
  get<{
    score: number;
    judgment: string;
    distribution: { positive: number; negative: number; neutral: number };
  }>("/api/news/sentiment");

// ============ Stock Analysis ============
export interface StockAnalysis {
  code: string;
  name: string;
  fundamentalScore: number;
  technicalScore: number;
  capitalScore: number;
  sentimentScore: number;
  aiScore: number;
  currentPrice: number;
  change: number;
  changePct: number;
  klineData: {
    date: string;
    open: number;
    close: number;
    high: number;
    low: number;
    volume: number;
  }[];
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

export const fetchStockAnalysis = (code: string) =>
  get<StockAnalysis>(`/api/stock/${code}/analysis`);

export const fetchStockKline = (code: string, period: string = "day", limit: number = 120) =>
  get<
    {
      date: string;
      open: number;
      close: number;
      high: number;
      low: number;
      volume: number;
    }[]
  >(`/api/stock/${code}/kline?period=${period}&limit=${limit}`);

// ============ Backtest ============
export interface BacktestResult {
  strategyName: string;
  symbol?: string;
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
  trades: {
    date: string;
    code: string;
    name: string;
    action: "buy" | "sell";
    price: number;
    shares: number;
    amount: number;
    pnl?: number;
  }[];
  dataSource?: string;
}

export const runBacktest = (config: {
  strategy: string;
  startDate: string;
  endDate: string;
  stockPool: string;
  initialCapital: number;
  code?: string;
}) => post<BacktestResult>("/api/backtest/run", config);

// ============ AI Researcher ============
export interface AIReport {
  date: string;
  marketSummary: string;
  upReasons: string[];
  riskFactors: string[];
  focusStocks: {
    code: string;
    name: string;
    reason: string;
    risk: string;
  }[];
  sentimentScore: number;
  aiJudgment: "bullish" | "neutral" | "bearish";
  outlook: string;
  llmEnabled: boolean;
  model: string;
  generatedAt: string;
}

export interface StockAIAnalysis {
  code: string;
  name: string;
  summary: string;
  tags: string[];
  rating: string;
  outlook: string;
  risk: string;
  llmEnabled: boolean;
  model: string;
}

export const fetchAIReport = (refresh: boolean = false) =>
  get<AIReport>(`/api/ai-researcher/report?refresh=${refresh}`);

export const fetchStockAIAnalysis = (code: string) =>
  get<StockAIAnalysis>(`/api/ai-researcher/analyze?code=${code}`);

// ============ AI 投研助手（自由对话） ============
export interface ChatMsg {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatReply {
  reply: string;
  model: string;
  llmEnabled: boolean;
}

export const chatWithAI = (messages: ChatMsg[], model?: string) =>
  post<ChatReply>("/api/ai/chat", { messages, model });

// ============ ABu ML 预测（移植自 bbfamily/abu） ============
export interface AbuMLPrediction {
  code: string;
  symbol: string;
  horizon: number;
  direction: string;          // 看涨 / 看跌 / 数据不足
  confidence: number;         // 0~1
  testAccuracy: number;
  testF1: number;
  cvAccuracy: number;
  nSamples: number;
  featureImportance: { feature: string; importance: number }[];
  trainedAt: string;
  note: string;
}

export const predictWithAbuML = (code: string, horizon: number = 5) =>
  post<AbuMLPrediction>("/api/abu-ml/predict", { code, horizon });

// ============ 因子分析（移植自 hugo2046/QuantsPlaybook） ============
export interface FactorGroup {
  group: number;
  avgFactor: number;
  avgForwardReturn: number;
  count: number;
}

export interface FactorAnalysis {
  code: string;
  symbol: string;
  factor: string;
  factorLabel: string;
  horizon: number;
  ic: number;
  icir: number;
  icWinRate: number;
  longShortReturn: number;
  groups: FactorGroup[];
  latestFactor: number;
  latestSignal: string;
  nSamples: number;
  startDate: string;
  endDate: string;
  note: string;
}

export const analyzeFactor = (
  code: string,
  factor: string = "momentum",
  horizon: number = 20,
) => post<FactorAnalysis>("/api/factor/analyze", { code, factor, horizon });

// ============ 横截面因子研究（移植自 hugo2046/QuantsPlaybook） ============
export interface CSGroup {
  group: number;
  avgForwardReturn: number;
  count: number;
}

export interface CSPoint {
  date: string;
  ic: number;
  coverage: number;
}

export interface CrossSectionFactor {
  factor: string;
  factorLabel: string;
  index: string;
  horizon: number;
  sampleSize: number;
  nStocks: number;
  nDates: number;
  icMean: number;
  icStd: number;
  icir: number;
  icWinRate: number;
  longShortReturn: number;
  icSeries: CSPoint[];
  groups: CSGroup[];
  startDate: string;
  endDate: string;
  note: string;
}

export const analyzeFactorCrossSection = (params: {
  index?: string;
  factor?: string;
  horizon?: number;
  sampleSize?: number;
}) => post<CrossSectionFactor>("/api/factor/cross-sectional", {
  index: params.index ?? "sh000300",
  factor: params.factor ?? "momentum",
  horizon: params.horizon ?? 20,
  sampleSize: params.sampleSize ?? 50,
});

// ============ AI 智能选股 ============
export interface StockCandidate {
  code: string;
  name: string;
}

export interface ScreenResult {
  market: string;
  expression: string;
  count: number;
  candidates: StockCandidate[];
}

export interface AnalyzeResult {
  summary: string;
  dataSources: string[];
  dimensions: string[];
  reasons: string[];
  model: string;
  llmEnabled: boolean;
}

export interface SingleBacktest {
  code: string;
  name: string;
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  equityCurve: { date: string; value: number }[];
  error?: string;
}

export interface BacktestAggregate {
  count: number;
  avgTotalReturn: number;
  avgAnnualized: number;
  avgSharpe: number;
  avgMaxDrawdown: number;
  avgWinRate: number;
  profitCount: number;
  lossCount: number;
}

export interface AttributionResult {
  verdict: "success" | "failure";
  points: string[];
  model: string;
  llmEnabled: boolean;
}

export interface ReportResult {
  strategy: string;
  startDate: string;
  endDate: string;
  backtests: SingleBacktest[];
  aggregate: BacktestAggregate;
  attribution: AttributionResult;
}

export const screenStocks = (params: {
  market?: string;
  expression: string;
  limit?: number;
}) => post<ScreenResult>("/api/stock-picker/screen", {
  market: params.market ?? "a",
  expression: params.expression,
  limit: params.limit ?? 20,
});

export const analyzeSelection = (params: {
  market?: string;
  expression: string;
  candidates: StockCandidate[];
}) => post<AnalyzeResult>("/api/stock-picker/analyze", {
  market: params.market ?? "a",
  expression: params.expression,
  candidates: params.candidates ?? [],
});

export const runPickerReport = (params: {
  codes: string[];
  strategy?: string;
  startDate?: string;
  endDate?: string;
  stockPool?: string;
  initialCapital?: number;
}) => post<ReportResult>("/api/stock-picker/report", {
  codes: params.codes,
  strategy: params.strategy ?? "MA双均线交叉基准策略",
  startDate: params.startDate ?? "2024-01-01",
  endDate: params.endDate ?? "2026-07-10",
  stockPool: params.stockPool ?? "沪深300",
  initialCapital: params.initialCapital ?? 1_000_000,
});

// ============ 市场动态 ============
export interface HotStock {
  code: string;
  name: string;
  changePct: number;
  price: number;
  type: string;
}

export interface LhbEntry {
  code: string;
  name: string;
  rank: number;
  daysOnList: number;
  instSeats: number;
  instBuyAmt: string;
  buyRatio: string;
  totalBuyAmt: string;
  netBuyAmt: string;
  netRatio: string;
}

export interface MarketIndexQuote {
  code: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
  amount: number;
}

export interface StockRankingItem {
  code: string;
  name: string;
  price: number;
  changePct: number;
  amount?: number;
}

export interface StockRankings {
  topGainers: StockRankingItem[];
  topLosers: StockRankingItem[];
  topVolume: StockRankingItem[];
}

export interface MarketNewsItem {
  time: string;
  title: string;
  source: string;
  summary: string;
  type: string;
}

export interface SectorRanking {
  code: string;
  name: string;
  chg5d: number;
  chg20d: number;
  chg60d: number;
  chg120d: number;
  chg250d: number;
}

export interface CapitalFlow {
  date: string;
  mainNetFlow: number;
  jumboNetFlow: number;
  midNetFlow: number;
  smallNetFlow: number;
  mainNetFlow5d: number;
  mainNetFlow20d: number;
}

// v1.3.1: 市场宽度 / 涨跌分布
export interface BreadthDistribution {
  label: string;
  count: number;
  percent: number;
}

export interface MarketBreadthSingle {
  market: string;
  marketName: string;
  total: number;
  upCount: number;
  downCount: number;
  flatCount: number;
  limitUp: number;
  limitDown: number;
  breadthPct: number;
  distribution: BreadthDistribution[];
}

export interface MarketBreadth {
  timestamp: string;
  date: string;
  shanghai: MarketBreadthSingle | null;
  shenzhen: MarketBreadthSingle | null;
  aggregate: {
    total: number;
    upCount: number;
    downCount: number;
    flatCount: number;
    limitUp: number;
    limitDown: number;
    breadthPct: number;
  };
}

export interface AShareDynamics {
  timestamp: string;
  marketIndices: MarketIndexQuote[];
  stockRankings: StockRankings;
  hotStocks: HotStock[];
  lhb: LhbEntry[];
  sectorRankings: SectorRanking[];
  capitalFlow: CapitalFlow;
  marketNews: MarketNewsItem[];
  marketBreadth: MarketBreadth;
}

export interface IntlHeadline {
  id: string;
  title: string;
  titleZh: string;
  source: string;
  link: string;
  published: string;
  credibility: "high" | "medium" | "low" | "";
  verificationNote: string;
}

export interface InternationalNews {
  timestamp: string;
  generatedAt: string;
  summaryText: string;
  headlines: IntlHeadline[];
  sourceCount: number;
  sources: string[];
  verifiedCount: number;
  highCredibilityCount: number;
}

export const getAShareDynamics = () =>
  get<AShareDynamics>("/api/market-dynamics/a-share");

export const getInternationalNews = (force?: boolean) =>
  get<InternationalNews>(
    `/api/market-dynamics/international-news${force ? "?force=true" : ""}`,
  );

// ============================================================
// 个股详情
// ============================================================
export interface StockProfile {
  code: string;
  name: string;
  listedDate: string;
  business: string;
  website: string;
  industry: string;
  sector: string;
  issuePrice: string;
  regCapital: string;
  establishDate: string;
  chairman: string;
  regAddress: string;
  officeAddress: string;
  tel: string;
  email: string;
}

export interface FinanceRow {
  _date: string;
  [key: string]: string;
}

export interface StockFinance {
  lrb: FinanceRow[];
  zcfz: FinanceRow[];
  xjll: FinanceRow[];
}

export interface StockNewsItem {
  time: string;
  id: string;
  title: string;
  url: string;
  src: string;
  summary: string;
}

export interface StockDetail {
  code: string;
  name: string;
  timestamp: string;
  profile: StockProfile;
  finance: StockFinance;
  news: StockNewsItem[];
  marketNews: StockNewsItem[];
}

export const getStockDetail = (code: string, force = false) =>
  get<StockDetail>(
    `/api/stock-detail/${code}${force ? "?force=true" : ""}`,
  );

// ============================================================
// v1.0 新增：市场温度 + AI Agent + 预警
// ============================================================
export interface TemperatureDimension {
  score: number;
  label: string;
  detail: Record<string, number>;
}

export interface MarketTemperature {
  timestamp: string;
  date: string;
  score: number;
  riskLevel: string;
  riskLabel: string;
  valuation: TemperatureDimension;
  sentiment: TemperatureDimension;
  capital: TemperatureDimension;
  technical: TemperatureDimension;
  weights: Record<string, number>;
}

export interface TemperatureHistory {
  temperature: {
    date: string;
    score: number;
    valuation: number;
    sentiment: number;
    capital: number;
    technical: number;
    riskLevel: string;
  }[];
  days: number;
}

export interface MarketJudgment {
  date: string;
  timestamp: string;
  marketTrend: string;
  marketSummary: string;
  policyDirection: string;
  liquidity: string;
  style: string;
  strongSectors: string[];
  weakSectors: string[];
  hotThemes: string[];
  rotationSignal: string;
  sectorSummary: string;
  positionAdvice: string;
  sectorAllocation: { sector: string; weight: number }[];
  recommendedStrategies: string[];
  riskStars: number;
  keyRisks: string[];
  actionPlan: string;
  aiScore: number;
  temperatureScore: number;
  model: string;
  generatedBy: string;
}

export interface AlertEntry {
  id: number;
  type: string;
  severity: string;
  code: string;
  title: string;
  message: string;
  isRead: boolean;
  createdAt: string;
}

export interface AlertsResponse {
  alerts: AlertEntry[];
  total: number;
  types: { info: number; warning: number; critical: number };
}

export const getMarketTemperature = (force?: boolean) =>
  get<MarketTemperature>(
    `/api/market-temperature${force ? "?force=true" : ""}`,
  );

export const getTemperatureHistory = (days?: number) =>
  get<TemperatureHistory>(`/api/market-temperature/history?days=${days ?? 30}`);

export const getMarketJudgment = (force?: boolean) =>
  fetch(
    `${API_BASE}/api/ai-agent/market-judgment${force ? "?force=true" : ""}`,
    { method: "POST" },
  ).then((r) => r.json()) as Promise<MarketJudgment>;

export const getAlerts = (limit?: number, type?: string) =>
  get<AlertsResponse>(
    `/api/alerts?limit=${limit ?? 50}${type ? `&type=${type}` : ""}`,
  );

// ============================================================
// v1.0 Dashboard V2 — 六屏矩阵
// ============================================================
export interface KlineBar {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

export interface DashboardV2KlineSignals {
  watchlist: string[];
  klineData: Record<string, KlineBar[]>;
}

export interface DashboardV2CapitalFlow {
  mainForce: Record<string, unknown>;
  sectorRankings: Record<string, unknown>;
}

export interface DashboardV2Portfolio {
  totalAssets: number;
  todayPnl: number;
  todayPnlPct: number;
  totalPnl: number;
  positions: Record<string, unknown>[];
  equityCurve: { date: string; value: number }[];
  dataSource: string;
}

export interface DashboardV2Data {
  indices: {
    code: string;
    name: string;
    value: number;
    change: number;
    changePct: number;
    volume: string;
    sparkline: number[];
  }[];
  temperature: MarketTemperature;
  judgment: MarketJudgment;
  capitalFlow: DashboardV2CapitalFlow;
  alerts: { total: number; items: AlertEntry[] };
  klineSignals: DashboardV2KlineSignals;
  portfolio: DashboardV2Portfolio;
  _meta: { westockAvailable: boolean; timestamp: string };
}

export const fetchDashboardV2 = () => get<DashboardV2Data>("/api/dashboard/v2");

// ============================================================
// v1.0 Phase 3: 多因子评分模型
// ============================================================
export interface FactorDimensionScore {
  score: number;
  label: string;
  subFactors: Record<string, number>;
}

export interface FactorScoreResult {
  code: string;
  name: string;
  industry: string;
  totalScore: number;
  percentile: number;
  rank: number;
  universeSize: number;
  dimensions: Record<string, FactorDimensionScore>;
  dataTimestamp: string;
  note: string;
}

export interface BatchFactorScore {
  results: FactorScoreResult[];
  universeSize: number;
  topCodes: string[];
  dataTimestamp: string;
}

export interface FactorICItem {
  ic: number;
  pValue: number;
  label: string;
  significant: boolean;
}

export interface ICAnalysisResult {
  factors: Record<string, FactorICItem>;
  sampleSize: number;
  note: string;
}

export const getFactorScore = (code: string) =>
  get<FactorScoreResult>(`/api/multi-factor/score?code=${code}`);

export const batchFactorScore = (codes: string[]) =>
  post<BatchFactorScore>("/api/multi-factor/batch", { codes });

export const getFactorRanking = (dimension?: string, limit?: number) =>
  get<BatchFactorScore>(
    `/api/multi-factor/ranking?limit=${limit ?? 20}${dimension ? `&dimension=${dimension}` : ""}`,
  );

export const getFactorICAnalysis = () =>
  get<ICAnalysisResult>("/api/multi-factor/ic-analysis");

// ============================================================
// v1.1 Phase 4: 组合管理 + 预警中心
// ============================================================
export interface PortfolioOverview {
  totalValue: number;
  cash: number;
  positionValue: number;
  totalReturn: number;
  totalReturnAmount: number;
  todayPnl: number;
  todayPnlPct: number;
  initialCapital: number;
  positionCount: number;
}

export interface PortfolioPosition {
  code: string;
  name: string;
  shares: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  weight: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
}

export interface AttributionBreakdown {
  code: string;
  name: string;
  industry: string;
  portfolioWeight: number;
  benchmarkWeight: number;
  stockReturn: number;
  industryReturn: number;
  allocationEffect: number;
  selectionEffect: number;
  interactionEffect: number;
}

export interface PortfolioAttribution {
  portfolioReturn: number;
  benchmarkReturn: number;
  excessReturn: number;
  allocation: number;
  selection: number;
  interaction: number;
  breakdown: AttributionBreakdown[];
}

export interface PortfolioRisk {
  var95: number;
  cvar95: number;
  var99: number;
  annualVolatility: number;
  sharpeRatio: number;
  maxDrawdown: number;
  method: string;
  confidence: string;
}

export interface RebalanceAdviceItem {
  industry: string;
  currentWeight: number;
  targetWeight: number;
  drift: number;
  adjustAmount: number;
  action: string;
  severity: string;
}

export interface RebalanceAdvice {
  totalValue: number;
  advice: RebalanceAdviceItem[];
  summary: string;
  targetWeights: Record<string, number>;
  currentIndustryWeights: Record<string, number>;
}

export interface PortfolioOrder {
  id: number;
  code: string;
  name: string;
  direction: string;
  price: number;
  shares: number;
  amount: number;
  status: string;
  reason: string;
  createdAt: string;
}

export interface PortfolioFull {
  overview: PortfolioOverview;
  positions: PortfolioPosition[];
  risk: PortfolioRisk;
}

export interface SnapshotEntry {
  date: string;
  totalValue: number;
  cash: number;
  positionValue: number;
  dailyPnl: number;
  dailyPnlPct: number;
  cumulativePnl: number;
  cumulativePnlPct: number;
}

export const getPortfolioOverview = () =>
  get<PortfolioOverview>("/api/portfolio/overview");

export const getPortfolioPositions = () =>
  get<PortfolioPosition[]>("/api/portfolio/positions");

export const getPortfolioAttribution = () =>
  get<PortfolioAttribution>("/api/portfolio/attribution");

export const getPortfolioRisk = (confidence?: number) =>
  get<PortfolioRisk>(`/api/portfolio/risk${confidence ? `?confidence=${confidence}` : ""}`);

export const getRebalanceAdvice = () =>
  get<RebalanceAdvice>("/api/portfolio/rebalance");

export const placePortfolioOrder = (params: {
  code: string;
  name: string;
  direction: string;
  shares: number;
  price?: number;
  reason?: string;
}) => post<PortfolioOrder & { message?: string; error?: string; status: string }>(
  "/api/portfolio/order",
  params,
);

export const getPortfolioOrders = (limit?: number) =>
  get<PortfolioOrder[]>(`/api/portfolio/orders?limit=${limit ?? 50}`);

export const cancelPortfolioOrder = (orderId: number) =>
  fetch(`${API_BASE}/api/portfolio/order/${orderId}`, {
    method: "DELETE",
  }).then((r) => r.json());

export const getPortfolioFull = () =>
  get<PortfolioFull>("/api/portfolio/full");

export const getPortfolioSnapshots = (days?: number) =>
  get<SnapshotEntry[]>(`/api/portfolio/snapshots?days=${days ?? 30}`);

// ── 预警中心扩展 ──
export const markAlertRead = (alertId: number) =>
  fetch(`${API_BASE}/api/alerts/mark-read/${alertId}`, {
    method: "POST",
  }).then((r) => r.json());

export const markAllAlertsRead = () =>
  fetch(`${API_BASE}/api/alerts/mark-all-read`, {
    method: "POST",
  }).then((r) => r.json());

// ============================================================
// v1.2 Phase 5: 策略优化器 + 组合回测 + 压力测试
// ============================================================

export interface OptimizeGridItem {
  shortWindow: number;
  longWindow: number;
  totalReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  calmarRatio: number;
}

export interface OptimizeResult {
  strategy: string;
  symbol: string;
  metric: string;
  bestParams: { shortWindow: number; longWindow: number };
  bestScore: number;
  allResults: OptimizeGridItem[];
  totalCombinations: number;
}

export interface PortfolioIndividualResult {
  strategy: string;
  symbol: string;
  totalReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
}

export interface PortfolioBacktestResult {
  weightScheme: string;
  nStrategies: number;
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  strategies: string[];
  symbols: string[];
  weights: number[];
  individualResults: PortfolioIndividualResult[];
  equityCurve: { date: string; value: number }[];
}

export interface StressTestScenario {
  scenario: string;
  description: string;
  peakToTrough: number;
  recoveryDays: number;
  finalReturn: number;
  survived: boolean;
}

export interface StressTestResult {
  symbol: string;
  initialCapital: number;
  scenarios: StressTestScenario[];
  totalScenarios: number;
}

export const optimizeParams = (config: {
  strategy?: string;
  symbol?: string;
  startDate?: string;
  endDate?: string;
  metric?: "sharpe" | "total_return" | "calmar";
}) => post<OptimizeResult>("/api/backtest/optimize", {
  strategy: config.strategy ?? "MA双均线交叉基准策略",
  symbol: config.symbol ?? "sh000300",
  startDate: config.startDate ?? "2024-01-01",
  endDate: config.endDate ?? "2026-07-10",
  metric: config.metric ?? "sharpe",
});

export const runPortfolioBacktest = (config: {
  strategies: string[];
  symbols: string[];
  startDate?: string;
  endDate?: string;
  initialCapital?: number;
  weightScheme?: "equal" | "sharpe_weighted" | "inverse_volatility";
}) => post<PortfolioBacktestResult>("/api/backtest/portfolio", {
  strategies: config.strategies,
  symbols: config.symbols,
  startDate: config.startDate ?? "2024-01-01",
  endDate: config.endDate ?? "2026-07-10",
  initialCapital: config.initialCapital ?? 1_000_000,
  weightScheme: config.weightScheme ?? "equal",
});

export const runStressTest = (symbol?: string, initialCapital?: number) =>
  get<StressTestResult>(
    `/api/backtest/stress-test?symbol=${symbol ?? "sh000300"}&initialCapital=${initialCapital ?? 1_000_000}`
  );

// ============================================================
// v1.3: 机构维度聚合 + 全市场实时数据 API
// ============================================================

export interface InstitutionLhbEntry {
  code: string;
  name: string;
  netBuyAmt: string;
  buyRatio: string;
  instSeats: number;
}

export interface InstitutionActivity {
  score: number;
  level: string;
  lhbCount: number;
  lhbTotalBuy: number;
  mainDirection: string;
  mainIntensity: number;
  mainFlow5d: number;
  mainFlow20d: number;
}

export interface InstitutionPositions {
  topInstitutionBuys: InstitutionLhbEntry[];
  hotSectors: { name: string; chg5d: number }[];
  coldSectors: { name: string; chg5d: number }[];
}

export interface InstitutionAggregate {
  timestamp: string;
  lhb: LhbEntry[];
  capitalFlow: CapitalFlow;
  northbound: { today: number; todayDesc: string; recent: number[] };
  institutionPositions: InstitutionPositions;
  institutionActivity: InstitutionActivity;
}

export const getInstitutionAggregate = () =>
  get<InstitutionAggregate>("/api/institution/aggregate");

export const getInstitutionActivity = () =>
  get<InstitutionActivity>("/api/institution/activity");

export const getNorthboundFlow = () =>
  get<{ today: number; todayDesc: string }>("/api/institution/northbound");

// 市场动态单维度 API
export const getMarketIndices = () =>
  get<MarketIndexQuote[]>("/api/market-dynamics/a-share/indices");

export const getStockRankings = () =>
  get<StockRankings>("/api/market-dynamics/a-share/stock-rankings");

export const getMarketNews = (limit?: number) =>
  get<MarketNewsItem[]>(`/api/market-dynamics/a-share/news?limit=${limit ?? 20}`);

export const getMarketBreadth = () =>
  get<MarketBreadth>("/api/market-dynamics/a-share/breadth");

// ============ 模拟盘交易系统 (Paper Trading) — 账户 (M1) ============
export interface PaperAccount {
  id: number;
  name: string;
  userId: number;
  initialCapital: number;
  cash: number;
  frozenCash: number;
  totalAssets: number;
  totalPnl: number;
  todayPnl: number;
  totalPnlPct: number;
  positionValue: number;
  availableCash: number;
  positionRatio: number;
  maxDrawdown: number;
  sharpeRatio: number;
  winRate: number;
  profitLossRatio: number;
  status: string;
  createdAt: string;
}

export interface PaperAccountMetrics {
  totalAssets: number;
  todayPnl: number;
  todayPnlPct: number;
  totalPnl: number;
  totalPnlPct: number;
  maxDrawdown: number;
  sharpeRatio: number;
  winRate: number;
  availableCash: number;
  positionValue: number;
  positionRatio: number;
  profitLossRatio: number;
}

export const fetchPaperAccounts = (username?: string) =>
  get<PaperAccount[]>(
    `/api/paper/account${username ? `?username=${encodeURIComponent(username)}` : ""}`
  );
export const createPaperAccount = (body: {
  name: string;
  initialCapital: number;
  preset?: string;
  username?: string;
}) => post<PaperAccount>("/api/paper/account", body);
export const fetchPaperAccount = (id: number) => get<PaperAccount>(`/api/paper/account/${id}`);
export const fetchPaperAccountMetrics = (id: number) =>
  get<PaperAccountMetrics>(`/api/paper/account/${id}/metrics`);

export interface AccountOverviewItem {
  id: number;
  name: string;
  totalAssets: number;
  totalPnl: number;
  totalPnlPct: number;
  positionValue: number;
  positionRatio: number;
  status: string;
}

export interface AccountOverview {
  totalAccounts: number;
  totalAssets: number;
  totalPnl: number;
  totalPnlPct: number;
  totalPositionValue: number;
  totalCash: number;
  activeCount: number;
  accounts: AccountOverviewItem[];
}

export interface PaperDailyReview {
  id: number;
  accountId: number;
  date: string;
  summary: string;
  tradesSummary: Record<string, unknown>;
  marketSummary: string;
  pnlSummary: Record<string, unknown>;
  performance: Record<string, unknown>;
  decisions: unknown[];
  generatedBy: string;
  createdAt: string;
}

export const fetchLatestReview = (accountId: number) =>
  get<PaperDailyReview>(`/api/paper/daily-review/${accountId}/latest`);

export const fetchReviewHistory = (accountId: number, limit = 20) =>
  get<PaperDailyReview[]>(`/api/paper/daily-review/${accountId}/list?limit=${limit}`);

export const generateReview = (accountId: number) =>
  post<PaperDailyReview>(`/api/paper/daily-review/${accountId}/generate`, {});

export const fetchAccountOverview = (username?: string) =>
  get<AccountOverview>(
    `/api/paper/account/overview${username ? `?username=${encodeURIComponent(username)}` : ""}`,
  );

export const updatePaperAccount = (id: number, body: {
  name?: string;
  initialCapital?: number;
}) => put<PaperAccount>(`/api/paper/account/${id}`, body);

export const deletePaperAccount = (id: number): Promise<{ deleted: boolean }> =>
  fetch(`${API_BASE}/api/paper/account/${id}`, { method: "DELETE" }).then((r) => r.json());

// ============ 模拟盘交易系统 (Paper Trading) — 行情 (M2) ============
export interface PaperQuote {
  code: string;
  name: string;
  price: number;
  prevClose: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  amount: number;
  turnover: number;
  amplitude: number;
  change: number;
  changePct: number;
  time: string;
  dataSource: string;
}

export interface PaperOrderBookLevel {
  price: number;
  volume: number;
}
export interface PaperOrderBook {
  code: string;
  name: string;
  bids: PaperOrderBookLevel[]; // 买一~买五
  asks: PaperOrderBookLevel[]; // 卖一~卖五
  time: string;
  dataSource: string;
}

export interface PaperKlinePoint {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}
export interface PaperKline {
  code: string;
  name: string;
  period: string;
  points: PaperKlinePoint[];
  dataSource: string;
}

export interface PaperSector {
  code: string;
  name: string;
  changePct: number;
  leader: string;
  leaderCode: string;
  dataSource: string;
}

export interface PaperMarketStatus {
  akshareAvailable: boolean;
  networkReachable: boolean;
  mode: string;
  cacheEntries: number;
  note?: string;
}

export const fetchPaperQuote = (code: string) =>
  get<PaperQuote>(`/api/paper/market/quote/${code}`);
export const fetchPaperOrderBook = (code: string) =>
  get<PaperOrderBook>(`/api/paper/market/orderbook/${code}`);
export const fetchPaperKline = (code: string, period = "day", limit = 120) =>
  get<PaperKline>(`/api/paper/market/kline/${code}?period=${period}&limit=${limit}`);
export const fetchPaperSectors = (kind: "industry" | "concept" = "industry") =>
  get<PaperSector[]>(`/api/paper/market/sectors?kind=${kind}`);
export const fetchPaperMarketStatus = () =>
  get<PaperMarketStatus>("/api/paper/market/status");

// ============ 模拟盘交易系统 (Paper Trading) — 订单 / 持仓 (M3) ============
export interface PaperOrder {
  id: number;
  accountId: number;
  code: string;
  name: string;
  direction: "buy" | "sell";
  orderType: string; // limit/market/stop_profit/stop_loss/grid/ai
  price: number;
  quantity: number;
  filledQuantity: number;
  avgFillPrice: number;
  amount: number;
  fee: number;
  status: string; // pending/partial/filled/cancelled/expired
  source: string;
  triggerPrice: number;
  parentId: number;
  createdAt: string;
  updatedAt: string;
}

export interface PaperPosition {
  accountId: number;
  code: string;
  name: string;
  industry: string;
  shares: number;
  sellableShares: number;
  costPrice: number;
  buyPrice: number;
  currentPrice: number;
  marketValue: number;
  pnlAmount: number;
  pnlPct: number;
  holdDays: number;
  positionRatio: number;
  stopLossPrice?: number; // 止损价（M7 AI 自动交易回写）
  takeProfitPrice?: number; // 止盈价（M7 AI 自动交易回写）
}

export type PaperOrderType = "limit" | "market" | "stop_profit" | "stop_loss" | "grid" | "ai";

export const createPaperOrder = (body: {
  accountId: number;
  code: string;
  name?: string;
  direction: "buy" | "sell";
  orderType: PaperOrderType;
  price?: number;
  quantity: number;
  triggerPrice?: number;
  tranches?: number;
  gridUpper?: number;
  gridLower?: number;
  gridStep?: number;
  gridQtyPer?: number;
  source?: string;
}) => post<PaperOrder[]>("/api/paper/order", body);
export const fetchPaperOrders = (accountId: number, status?: string) =>
  get<PaperOrder[]>(`/api/paper/order/${accountId}${status ? `?status=${status}` : ""}`);
export const cancelPaperOrder = (accountId: number, orderId: number) =>
  post<PaperOrder>(`/api/paper/order/${accountId}/${orderId}/cancel`, {});
export const matchPaperOrders = (accountId?: number) =>
  post<{ matched: number }>(`/api/paper/order/match${accountId ? `?account_id=${accountId}` : ""}`, {});
export const fetchPaperPositions = (accountId: number) =>
  get<PaperPosition[]>(`/api/paper/position/${accountId}`);
export const rolloverPaperDay = (accountId: number) =>
  post<{ ok: boolean }>(`/api/paper/position/${accountId}/rollover`, {});

export interface PaperPositionIndustry {
  industry: string;
  marketValue: number;
  ratio: number;
}

export interface PaperPositionSummary {
  accountId: number;
  positionCount: number;
  totalMarketValue: number;
  totalCost: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  realizedPnl: number;
  todayPnl: number;
  todayPnlPct: number;
  totalPnl: number;
  maxPositionRatio: number;
  top3Ratio: number;
  industryDistribution: PaperPositionIndustry[];
}

export const fetchPaperPositionSummary = (accountId: number) =>
  get<PaperPositionSummary>(`/api/paper/position/${accountId}/summary`);
export const refreshPaperPositions = (accountId: number) =>
  post<PaperPosition[]>(`/api/paper/position/${accountId}/refresh`, {});

// ====================== 模拟盘风险（M5） ======================
export interface PaperRiskConfig {
  accountId: number;
  enabled: boolean;
  maxPositionRatio: number;     // 0-1
  maxTotalPositionRatio: number; // 0-1
  maxSingleAmount: number;       // 元
  maxDailyLoss: number;          // 元
  stopLossRatio: number;         // 0-1
  allowShort: boolean;
}

export interface PaperRiskMetrics {
  accountId: number;
  totalAssets: number;
  positionValue: number;
  totalPositionRatio: number;    // 0-1
  maxPositionRatio: number;      // 0-1
  todayPnl: number;
  dailyLoss: number;
  dailyLossRatio: number;        // 0-1
  concentrationStatus: string;   // ok / warn / breach
  stopLossStatus: string;
  dailyLossStatus: string;
  overallStatus: string;
  breaches: string[];
  configSnapshot: PaperRiskConfig;
}

export interface PaperRiskEvent {
  id: number;
  accountId: number;
  code: string;
  eventType: string;
  level: string;
  message: string;
  detail: Record<string, unknown>;
  acked: boolean;
  createdAt: string;
}

export const fetchPaperRiskConfig = (accountId: number) =>
  get<PaperRiskConfig>(`/api/paper/risk/${accountId}/config`);
export const updatePaperRiskConfig = (accountId: number, body: Partial<PaperRiskConfig>) =>
  put<PaperRiskConfig>(`/api/paper/risk/${accountId}/config`, body);
export const fetchPaperRiskMetrics = (accountId: number) =>
  get<PaperRiskMetrics>(`/api/paper/risk/${accountId}/metrics`);
export const fetchPaperRiskEvents = (accountId: number, limit = 100) =>
  get<PaperRiskEvent[]>(`/api/paper/risk/${accountId}/events?limit=${limit}`);
export const scanPaperRisk = (accountId: number) =>
  post<{ recorded: number }>(`/api/paper/risk/${accountId}/scan`, {});

// ====================== 智能风控中心（risk center 增强） ======================
export type PaperRiskRuleType =
  | "SECTOR_CONCENTRATION"
  | "MAX_DRAWDOWN"
  | "LEVERAGE"
  | "BLACKLIST"
  | "OVERNIGHT_LIMIT"
  | "CUSTOM";

export interface PaperRiskRule {
  id: number;
  accountId: number | null;
  name: string;
  ruleType: PaperRiskRuleType;
  threshold: number;
  scope: string; // account / global
  enabled: boolean;
  severity: string; // warn / high / critical
  detail: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface PaperRiskReport {
  accountId: number;
  generatedAt: string;
  overallStatus: string; // ok / warn / breach
  score: number; // 风险评分 0-100
  summary: string;
  metrics: PaperRiskMetrics;
  activeRules: number;
  triggeredRules: {
    ruleId: number;
    name: string;
    ruleType: PaperRiskRuleType;
    severity: string;
    message: string;
  }[];
  topBreaches: string[];
  suggestions: string[];
}

export const fetchPaperRiskRules = (accountId: number) =>
  get<PaperRiskRule[]>(`/api/paper/risk/${accountId}/rules`);
export const createPaperRiskRule = (
  accountId: number,
  body: {
    name: string;
    ruleType: PaperRiskRuleType;
    threshold?: number;
    scope?: string;
    enabled?: boolean;
    severity?: string;
    detail?: Record<string, unknown>;
  },
) =>
  post<PaperRiskRule>(`/api/paper/risk/${accountId}/rules`, {
    name: body.name,
    ruleType: body.ruleType,
    threshold: body.threshold ?? 0,
    scope: body.scope ?? "account",
    enabled: body.enabled ?? true,
    severity: body.severity ?? "warn",
    detail: body.detail ?? {},
  });
export const updatePaperRiskRule = (
  accountId: number,
  ruleId: number,
  body: {
    name: string;
    ruleType: PaperRiskRuleType;
    threshold?: number;
    scope?: string;
    enabled?: boolean;
    severity?: string;
    detail?: Record<string, unknown>;
  },
) =>
  put<PaperRiskRule>(`/api/paper/risk/${accountId}/rules/${ruleId}`, {
    name: body.name,
    ruleType: body.ruleType,
    threshold: body.threshold ?? 0,
    scope: body.scope ?? "account",
    enabled: body.enabled ?? true,
    severity: body.severity ?? "warn",
    detail: body.detail ?? {},
  });
export const deletePaperRiskRule = (accountId: number, ruleId: number) =>
  fetch(`${API_BASE}/api/paper/risk/${accountId}/rules/${ruleId}`, {
    method: "DELETE",
  }).then((r) => r.json());
export const ackPaperRiskEvent = (accountId: number, eventId: number) =>
  post<{ acked: boolean }>(
    `/api/paper/risk/${accountId}/events/${eventId}/ack`,
    {},
  );
export const ackAllPaperRiskEvents = (accountId: number) =>
  post<{ acked: number }>(`/api/paper/risk/${accountId}/events/ack-all`, {});
export const fetchPaperRiskReport = (accountId: number) =>
  get<PaperRiskReport>(`/api/paper/risk/${accountId}/report`);

// ====================== 模拟盘 股票池自动维护 (M179) ======================
export type PaperPoolHealth = "unknown" | "ok" | "suspended" | "st" | "illiquid";
export type PaperPoolSyncSource = "manual" | "sector" | "concept" | "index";

export interface PaperPoolItem {
  id: number;
  accountId: number;
  code: string;
  name: string;
  category: string;
  note: string;
  pinned: boolean;
  health: PaperPoolHealth;
  source: string;
  lastChecked: string | null;
  createdAt: string;
}

export interface PaperPoolConfig {
  accountId: number;
  autoSync: boolean;
  syncSource: PaperPoolSyncSource;
  syncName: string;
  removeSuspended: boolean;
  removeSt: boolean;
  removeIlliquid: boolean;
  minTurnover: number;
  maxSize: number;
  updatedAt: string | null;
}

export interface PaperPoolChangeLog {
  id: number;
  accountId: number;
  code: string;
  name: string;
  action: string; // add / remove
  reason: string;
  source: string;
  createdAt: string;
}

export interface PaperPoolMaintainResult {
  accountId: number;
  checked: number;
  added: number;
  removed: number;
  skippedPinned: number;
  details: { code: string; action: string; reason: string }[];
}

export interface PaperPoolSources {
  sector: string[];
  concept: string[];
}

export const fetchPaperPoolItems = (accountId: number) =>
  get<PaperPoolItem[]>(`/api/paper/pool/${accountId}/items`);

export const addPaperPoolItem = (
  accountId: number,
  body: { code: string; name?: string; category?: string; note?: string; pinned?: boolean; source?: string },
) =>
  post<PaperPoolItem>(`/api/paper/pool/${accountId}/items`, {
    code: body.code,
    name: body.name ?? "",
    category: body.category ?? "",
    note: body.note ?? "",
    pinned: body.pinned ?? false,
    source: body.source ?? "manual",
  });

export const updatePaperPoolItem = (
  accountId: number,
  itemId: number,
  body: { category?: string; note?: string; pinned?: boolean },
) =>
  put<PaperPoolItem>(`/api/paper/pool/${accountId}/items/${itemId}`, {
    category: body.category,
    note: body.note,
    pinned: body.pinned,
  });

export const deletePaperPoolItem = (accountId: number, itemId: number) =>
  fetch(`${API_BASE}/api/paper/pool/${accountId}/items/${itemId}`, { method: "DELETE" }).then((r) => r.json());

export const fetchPaperPoolConfig = (accountId: number) =>
  get<PaperPoolConfig>(`/api/paper/pool/${accountId}/config`);

export const updatePaperPoolConfig = (accountId: number, body: Partial<PaperPoolConfig>) =>
  put<PaperPoolConfig>(`/api/paper/pool/${accountId}/config`, {
    autoSync: body.autoSync ?? false,
    syncSource: body.syncSource ?? "manual",
    syncName: body.syncName ?? "",
    removeSuspended: body.removeSuspended ?? true,
    removeSt: body.removeSt ?? true,
    removeIlliquid: body.removeIlliquid ?? false,
    minTurnover: body.minTurnover ?? 1.0,
    maxSize: body.maxSize ?? 0,
  });

export const runPaperPoolMaintain = (accountId: number) =>
  post<PaperPoolMaintainResult>(`/api/paper/pool/${accountId}/maintain`, {});

export const fetchPaperPoolChangelog = (accountId: number, limit = 100) =>
  get<PaperPoolChangeLog[]>(`/api/paper/pool/${accountId}/changelog?limit=${limit}`);

export const fetchPaperPoolSources = () =>
  get<PaperPoolSources>(`/api/paper/pool/sources`);

// ====================== 模拟盘 资金与收益曲线 / 统计中心 (M6) ======================
export interface PaperEquityPoint {
  date: string;
  totalAssets: number;
  cash: number;
  positionValue: number;
  dailyPnl: number;
  dailyPnlPct: number;
  cumulativePnl: number;
  cumulativePnlPct: number;
}

export interface PaperAccountStatistics {
  accountId: number;
  initialCapital: number;
  currentAssets: number;
  cumulativePnl: number;
  cumulativePnlPct: number;
  totalReturn: number;
  annualizedReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  winRate: number;
  profitLossRatio: number;
  tradeCount: number;
  winCount: number;
  lossCount: number;
  avgWin: number;
  avgLoss: number;
  snapshotCount: number;
}

export const fetchPaperEquity = (accountId: number, days?: number) =>
  get<PaperEquityPoint[]>(`/api/paper/stats/${accountId}/equity${days ? `?days=${days}` : ""}`);
export const fetchPaperStatistics = (accountId: number) =>
  get<PaperAccountStatistics>(`/api/paper/stats/${accountId}/statistics`);
export const takePaperSnapshot = (accountId: number) =>
  post<PaperEquityPoint>(`/api/paper/stats/${accountId}/snapshot`, {});
export const refreshPaperStats = (accountId: number) =>
  post<PaperAccountStatistics>(`/api/paper/stats/${accountId}/refresh`, {});
export const seedPaperBaseline = (accountId: number) =>
  post<PaperEquityPoint>(`/api/paper/stats/${accountId}/seed`, {});

// ====================== 模拟盘 AI 自动交易 (M7) ======================
export interface PaperStrategyConfig {
  id: string;
  accountId: number;
  name: string;
  description: string;
  enabled: boolean;
  params: Record<string, unknown>;
  metrics: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface PaperSignal {
  id: number;
  accountId: number;
  code: string;
  name: string;
  signalType: "buy" | "sell" | "hold";
  strength: number; // 0-100
  source: string; // ai / rule
  reason: string;
  priceTarget: number;
  stopLoss: number;
  takeProfit: number;
  riskScore: number;
  createdAt: string;
}

export interface PaperAILog {
  id: number;
  accountId: number;
  logType: string;
  level: string;
  message: string;
  meta: Record<string, unknown>;
  createdAt: string;
}

export interface PaperAutoStatus {
  accountId: number;
  enabledStrategies: number;
  running: boolean;
  lastRunAt: string;
  lastRunSummary: Record<string, number>;
  dataSource: string;
  watchedCodes: number;
}

export const fetchPaperStrategies = (accountId: number) =>
  get<PaperStrategyConfig[]>(`/api/paper/auto/${accountId}/strategies`);
export const createPaperStrategy = (
  accountId: number,
  body: { name: string; description?: string; enabled?: boolean; params?: Record<string, unknown> },
) => post<PaperStrategyConfig>(`/api/paper/auto/${accountId}/strategies`, body);
export const togglePaperStrategy = (accountId: number, strategyId: string, enabled: boolean) =>
  post<PaperStrategyConfig>(
    `/api/paper/auto/${accountId}/strategies/${strategyId}/toggle`,
    { enabled },
  );
export const runPaperAutoTrade = (accountId: number, strategyId?: string) =>
  post<Record<string, unknown>>(
    `/api/paper/auto/${accountId}/run${strategyId ? `?strategy_id=${strategyId}` : ""}`,
    {},
  );
export const fetchPaperSignals = (accountId: number, limit = 50, code?: string) =>
  get<PaperSignal[]>(
    `/api/paper/auto/${accountId}/signals?limit=${limit}${code ? `&code=${code}` : ""}`,
  );
export const fetchPaperAILogs = (accountId: number, limit = 50) =>
  get<PaperAILog[]>(`/api/paper/auto/${accountId}/logs?limit=${limit}`);
export const fetchPaperAutoStatus = (accountId: number) =>
  get<PaperAutoStatus>(`/api/paper/auto/${accountId}/status`);
export const setPaperHoldingSLTP = (
  accountId: number,
  code: string,
  stopLossPrice: number,
  takeProfitPrice: number,
) =>
  post<PaperPosition>(
    `/api/paper/auto/${accountId}/holdings/sltp`,
    { code, stopLossPrice, takeProfitPrice },
  );

// ====================== M8 回测模块 ======================
export interface PaperBacktestTrade {
  date: string;
  code: string;
  action: string; // buy / sell
  price: number;
  shares: number;
  amount: number;
  pnl?: number;
}

export interface PaperBacktestRun {
  id: number;
  accountId: number | null;
  strategyName: string;
  symbol: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  calmarRatio: number;
  alpha: number;
  beta: number;
  winRate: number;
  totalTrades: number;
  equityCurve: { date: string; value: number }[];
  trades: PaperBacktestTrade[];
  dataSource: string; // westock / mock
  params: Record<string, unknown>;
  mode: string; // factor（因子/均线）/ event（事件驱动）
  createdAt: string;
}

export interface PaperBacktestStrategy {
  key: string;
  label: string;
}

export interface RunPaperBacktestBody {
  strategy?: string;
  stockPool?: string;
  code?: string | null;
  startDate?: string;
  endDate?: string;
  initialCapital?: number;
  strategyId?: string | null;
}

export const fetchPaperBacktestStrategies = () =>
  get<PaperBacktestStrategy[]>(`/api/paper/backtest/strategies`);

export const runPaperBacktest = (
  accountId: number | null,
  body: RunPaperBacktestBody,
) =>
  post<PaperBacktestRun>(`/api/paper/backtest/run`, {
    accountId,
    strategy: body.strategy ?? "均线交叉(MA5/MA20)",
    stockPool: body.stockPool ?? "沪深300",
    code: body.code ?? null,
    startDate: body.startDate ?? "",
    endDate: body.endDate ?? "",
    initialCapital: body.initialCapital ?? 1_000_000.0,
    strategyId: body.strategyId ?? null,
  });

export const fetchPaperBacktests = (accountId?: number | null, limit = 50) =>
  get<PaperBacktestRun[]>(
    `/api/paper/backtest/runs?${accountId ? `account_id=${accountId}&` : ""}limit=${limit}`,
  );

export const fetchPaperBacktest = (runId: number) =>
  get<PaperBacktestRun>(`/api/paper/backtest/runs/${runId}`);

// ====================== M181 事件驱动回测引擎 ======================
export interface PaperEventRule {
  side: "entry" | "exit";
  kind: string; // ma_cross / price_breakout / rsi / drawdown_stop / take_profit / hold_days
  params: Record<string, number>;
}

export interface PaperEventStrategy {
  key: string;
  label: string;
  rules: PaperEventRule[];
  risk: { stopLoss: number; takeProfit: number };
}

export interface RunEventBacktestBody {
  strategyName?: string;
  universe?: string[];
  code?: string | null;
  stockPool?: string;
  startDate?: string;
  endDate?: string;
  initialCapital?: number;
  rules: PaperEventRule[];
  risk?: { stopLoss: number; takeProfit: number };
  strategyId?: string | null;
}

export const fetchPaperEventStrategies = () =>
  get<PaperEventStrategy[]>(`/api/paper/backtest/event-strategies`);

export const runPaperEventBacktest = (
  accountId: number | null,
  body: RunEventBacktestBody,
) =>
  post<PaperBacktestRun>(`/api/paper/backtest/event-backtest`, {
    accountId,
    strategyName: body.strategyName ?? "事件驱动组合",
    universe: body.universe ?? [],
    code: body.code ?? null,
    stockPool: body.stockPool ?? "",
    startDate: body.startDate ?? "",
    endDate: body.endDate ?? "",
    initialCapital: body.initialCapital ?? 1_000_000.0,
    rules: body.rules,
    risk: body.risk ?? {},
    strategyId: body.strategyId ?? null,
  });

// ====================== 研究员 Agent（#182：自动挖掘因子、生成策略） ======================
export interface PaperFactorFinding {
  id: number;
  sessionId: number;
  name: string;
  factorType: string;                                // momentum/volatility/reversal/rsi/volume/quality
  description: string;
  direction: string;                                 // long / short / neutral
  score: number;                                     // 因子强度评分(0-100)
  detail: Record<string, unknown>;
  createdAt: string;
}

export interface PaperStrategyIdea {
  id: number;
  sessionId: number;
  accountId?: number | null;
  name: string;
  description: string;
  universe: string[];
  entryRules: PaperEventRule[];
  exitRules: PaperEventRule[];
  risk: { stopLoss?: number; takeProfit?: number };
  logic: string;
  expected: string;
  backtestRunId?: number | null;
  backtested: boolean;
  createdAt: string;
}

export interface PaperResearchSession {
  id: number;
  accountId?: number | null;
  universe: string[];
  mode: string;                                       // rule / llm
  model: string;
  summary: string;
  status: string;
  factors: PaperFactorFinding[];
  ideas: PaperStrategyIdea[];
  createdAt: string;
}

export interface RunResearchBody {
  accountId?: number | null;
  universe?: string[];                                // 空则用默认观察池
  useLlm?: boolean;
  maxIdeas?: number;
}

export interface RunResearchResult {
  session: PaperResearchSession;
  factorCount: number;
  ideaCount: number;
}

export const runPaperResearch = (body: RunResearchBody) =>
  post<RunResearchResult>(`/api/paper/research/run`, {
    accountId: body.accountId ?? null,
    universe: body.universe ?? [],
    useLlm: body.useLlm ?? false,
    maxIdeas: body.maxIdeas ?? 3,
  });

export const fetchPaperResearchSessions = (accountId?: number | null) =>
  get<PaperResearchSession[]>(
    `/api/paper/research/sessions${accountId ? `?account_id=${accountId}` : ""}`,
  );

export const fetchPaperResearchIdeas = (accountId?: number | null) =>
  get<PaperStrategyIdea[]>(
    `/api/paper/research/ideas${accountId ? `?account_id=${accountId}` : ""}`,
  );

export const deletePaperResearchIdea = (ideaId: number): Promise<{ deleted: boolean }> =>
  fetch(`${API_BASE}/api/paper/research/ideas/${ideaId}`, { method: "DELETE" }).then((r) => r.json());

export const backtestPaperResearchIdea = (ideaId: number, accountId?: number | null) =>
  post<{
    runId: number;
    mode: string;
    totalReturn: number;
    sharpeRatio: number;
    maxDrawdown: number;
    winRate: number;
    totalTrades: number;
  }>(`/api/paper/research/ideas/${ideaId}/backtest${accountId ? `?account_id=${accountId}` : ""}`, {});


// ====================== 策略市场 (Marketplace, #183) ======================

export interface PublishedStrategy {
  id: number;
  authorAccountId: number;
  name: string;
  description: string;
  sourceType: string;
  sourceId: number | null;
  entryRules: unknown[];
  exitRules: unknown[];
  risk: Record<string, unknown>;
  universe: string[];
  logic: string;
  performanceSnapshot: Record<string, unknown>;
  tags: string[];
  version: number;
  isPublished: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface MarketplaceListing {
  id: number;
  authorAccountId: number;
  name: string;
  description: string;
  sourceType: string;
  tags: string[];
  isPublished: boolean;
  avgRating: number;
  ratingCount: number;
  subscriberCount: number;
  performanceSnapshot: Record<string, unknown>;
  createdAt: string;
}

export interface MarketplaceLeaderboardEntry {
  publishedStrategyId: number;
  name: string;
  authorAccountId: number;
  avgRating: number;
  ratingCount: number;
  subscriberCount: number;
  compositeScore: number;
}

export interface MarketplaceRating {
  id: number;
  accountId: number;
  publishedStrategyId: number;
  score: number;
  review: string;
  createdAt: string;
}

export const publishStrategy = (body: {
  accountId: number;
  name: string;
  description?: string;
  sourceType?: string;
  sourceId?: number | null;
  entryRules?: unknown[];
  exitRules?: unknown[];
  risk?: Record<string, unknown>;
  universe?: string[];
  logic?: string;
  performanceSnapshot?: Record<string, unknown>;
  tags?: string[];
}) => post<PublishedStrategy>("/api/paper/strategy-marketplace/publish", body);

export const unpublishStrategy = (strategyId: number, accountId: number) =>
  post<{ unpublished: boolean }>(
    `/api/paper/strategy-marketplace/${strategyId}/unpublish?account_id=${accountId}`,
    {},
  );

export const fetchMarketplaceListings = (limit = 50, offset = 0) =>
  get<MarketplaceListing[]>(
    `/api/paper/strategy-marketplace/listing?limit=${limit}&offset=${offset}`,
  );

export const searchMarketplace = (tag: string, limit = 20) =>
  get<MarketplaceListing[]>(
    `/api/paper/strategy-marketplace/search?tag=${encodeURIComponent(tag)}&limit=${limit}`,
  );

export const fetchPublishedStrategy = (strategyId: number) =>
  get<PublishedStrategy>(`/api/paper/strategy-marketplace/${strategyId}`);

export const fetchMyPublishedStrategies = (accountId: number) =>
  get<PublishedStrategy[]>(
    `/api/paper/strategy-marketplace/my-published?account_id=${accountId}`,
  );

export const subscribeMarketplaceStrategy = (body: {
  accountId: number;
  publishedStrategyId: number;
}) =>
  post<{
    subId: number;
    localStrategyId: string;
    alreadySubscribed: boolean;
  }>("/api/paper/strategy-marketplace/subscribe", body);

export const unsubscribeMarketplaceStrategy = (
  accountId: number,
  publishedStrategyId: number,
) =>
  post<{ unsubscribed: boolean }>(
    `/api/paper/strategy-marketplace/unsubscribe?account_id=${accountId}&published_strategy_id=${publishedStrategyId}`,
    {},
  );

export const fetchMySubscriptions = (accountId: number) =>
  get<unknown[]>(
    `/api/paper/strategy-marketplace/my-subscriptions?account_id=${accountId}`,
  );

export const rateMarketplaceStrategy = (body: {
  accountId: number;
  publishedStrategyId: number;
  score: number;
  review?: string;
}) => post<MarketplaceRating>("/api/paper/strategy-marketplace/rate", body);

export const fetchMarketplaceRatings = (strategyId: number) =>
  get<MarketplaceRating[]>(
    `/api/paper/strategy-marketplace/${strategyId}/ratings`,
  );

export const fetchMarketplaceLeaderboard = (limit = 20) =>
  get<MarketplaceLeaderboardEntry[]>(
    `/api/paper/strategy-marketplace/leaderboard?limit=${limit}`,
  );


// ====================== 策略组合 (Portfolio, #184) ======================

export interface PortfolioAllocation {
  strategyId: string;
  weight: number;
}

export interface PortfolioResponse {
  id: number;
  accountId: number;
  name: string;
  description: string;
  allocation: PortfolioAllocation[];
  totalCapital: number;
  enabled: boolean;
  strategyCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface PortfolioRebalanceResponse {
  id: number;
  portfolioId: number;
  triggeredAt: string;
  reason: string;
  allocationsBefore: { strategyId: string; weight: number }[];
  allocationsAfter: { strategyId: string; weight: number }[];
  status: string;
  notes: string;
}

export const fetchPortfolios = (accountId: number) =>
  get<PortfolioResponse[]>(`/api/paper/portfolio?account_id=${accountId}`);

export const createPortfolio = (body: {
  accountId: number;
  name: string;
  description?: string;
  allocation?: PortfolioAllocation[];
  totalCapital?: number;
  enabled?: boolean;
}) => post<PortfolioResponse>("/api/paper/portfolio", body);

export const getPortfolio = (id: number) =>
  get<PortfolioResponse>(`/api/paper/portfolio/${id}`);

export const updatePortfolio = (id: number, body: {
  accountId: number;
  name: string;
  description?: string;
  allocation?: PortfolioAllocation[];
  totalCapital?: number;
  enabled?: boolean;
}) => put<PortfolioResponse>(`/api/paper/portfolio/${id}`, body);

export const deletePortfolio = (id: number): Promise<{ deleted: boolean }> =>
  fetch(`${API_BASE}/api/paper/portfolio/${id}`, { method: "DELETE" }).then((r) => r.json());

export const runPortfolio = (id: number) =>
  post<{ portfolioId: number; strategyResults: Record<string, string> }>(
    `/api/paper/portfolio/${id}/run`, {},
  );

export const rebalancePortfolio = (id: number, body: {
  accountId: number;
  name: string;
  allocation?: PortfolioAllocation[];
  totalCapital?: number;
}, reason = "") =>
  post<PortfolioRebalanceResponse>(
    `/api/paper/portfolio/${id}/rebalance?reason=${encodeURIComponent(reason)}`, body,
  );

export const fetchPortfolioRebalances = (id: number, limit = 20) =>
  get<PortfolioRebalanceResponse[]>(`/api/paper/portfolio/${id}/rebalances?limit=${limit}`);

// ============================================================
// 实时行情市场模块（app/market）— AI 量化实时数据支撑
// 端点前缀：/api/market/* ，WS：/ws/market/realtime
// ============================================================

// 实时行情（与后端 QuoteOut 对齐）
export interface MarketQuote {
  code: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
  amount: number;
  turnover: number;
  pe: number;
  pb: number;
  totalMv: number;
  floatMv: number;
  source: string;
}

// 技术指标（与 TechOut 对齐）
export interface MarketTech {
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  rsi14: number | null;
  macd: number | null;
  macdSignal: number | null;
  macdHist: number | null;
}

// 资金流（与 CapitalFlowOut 对齐）
export interface MarketCapitalFlow {
  code: string;
  available: boolean;
  mainIn: number;
  ultraLarge: number;
  large: number;
  medium: number;
  small: number;
  mainNetFlow5d: number;
}

// AI 评分（与 AIScoreOut 对齐；riskLevel: low|mid|high）
export interface MarketAIScore {
  score: number;
  techScore: number;
  fundScore: number;
  sentimentScore: number;
  momentum: number;
  volatility: number;
  riskLevel: "low" | "mid" | "high";
}

export interface MarketRealtimeItem {
  quote: MarketQuote;
  capitalFlow: MarketCapitalFlow | null;
  technicals: MarketTech;
  aiScore: MarketAIScore;
}

export interface MarketRealtimeResponse {
  ts: string;
  source: string;
  count: number;
  items: MarketRealtimeItem[];
}

// K 线（与 KlineBarOut 对齐）
export interface MarketKlineBar {
  dt: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
}

// 市场宽度（与 BreadthOut 对齐）
export interface MarketBreadth {
  total: number;
  upCount: number;
  downCount: number;
  flatCount: number;
  limitUp: number;
  limitDown: number;
  breadthPct: number;
}

// 数据源健康（与 SourceHealth 对齐）
export interface MarketSourceHealth {
  name: string;
  available: boolean;
  circuit: string; // closed | open | half_open
  lastUsed: boolean;
}

// 市场监控聚合（/api/market/monitor）
export interface MarketMonitorResponse {
  breadth: MarketBreadth;
  rankings: StockRankings;
  hotStocks: HotStock[];
  sectorRankings: SectorRanking[];
}

// 资金流聚合（/api/market/capital-flow）
export interface MarketCapitalFlowResponse {
  items: MarketCapitalFlow[];
  northbound: number | null;
  lhb: LhbEntry[];
}

// WS 推送的实时行情条目（与 Quote.to_dict() 对齐）
export interface MarketWSQuote {
  code: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
  amount: number;
  turnover: number;
  pe: number;
  pb: number;
  total_mv: number;
  float_mv: number;
  open: number;
  high: number;
  low: number;
  prev_close: number;
  source: string;
  ts: number;
}

export const fetchMarketRealtime = (codes: string[]) =>
  get<MarketRealtimeResponse>(
    `/api/market/realtime?codes=${codes.map((c) => encodeURIComponent(c)).join(",")}`,
  );

export const fetchMarketQuote = (code: string) =>
  get<MarketQuote>(`/api/market/quote/${encodeURIComponent(code)}`);

export const fetchMarketKline = (code: string, period = "day", limit = 120) =>
  get<MarketKlineBar[]>(
    `/api/market/kline?code=${encodeURIComponent(code)}&period=${period}&limit=${limit}`,
  );

export const fetchMarketCapitalFlow = (codes: string[] = []) =>
  get<MarketCapitalFlowResponse>(
    `/api/market/capital-flow?codes=${codes.map((c) => encodeURIComponent(c)).join(",")}`,
  );

export const fetchMarketMonitor = () => get<MarketMonitorResponse>("/api/market/monitor");

export const fetchMarketSources = () => get<MarketSourceHealth[]>("/api/market/sources");

// ============ Strategies ============
export interface ApiStrategy {
  id: string;
  name: string;
  type: string;
  status: "running" | "stopped" | "paused" | "archived" | "backtesting";
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  description: string;
  equityCurve: { date: string; value: number }[];
  createdAt: string;
}

export interface StrategyActionResult {
  id: string;
  status: string;
  message: string;
}

export const fetchStrategies = () => get<ApiStrategy[]>("/api/strategies/");

export const deleteStrategy = (id: string) =>
  del<{ ok: boolean; id: string; message: string }>(`/api/strategies/${id}`);

export const archiveStrategy = (id: string) =>
  post<StrategyActionResult>(`/api/strategies/${id}/archive`, {});

export const toggleStrategyApi = (id: string) =>
  post<StrategyActionResult>(`/api/strategies/${id}/toggle`, {});
