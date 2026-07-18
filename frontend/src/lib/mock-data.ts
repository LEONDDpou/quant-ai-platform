import type {
  AccountMetrics,
  MarketIndex,
  Position,
  Strategy,
  NewsItem,
  AIResearchReport,
} from "@/types";

// ==================== 账户指标 ====================
export const accountMetrics: AccountMetrics = {
  totalAssets: 2845620.50,
  todayPnl: 32580.32,
  todayPnlPct: 1.16,
  totalPnl: 545620.50,
  totalPnlPct: 23.72,
  annualizedReturn: 35.68,
  maxDrawdown: 8.32,
  winRate: 72.5,
  availableCash: 568230.10,
  positionValue: 2277390.40,
};

// ==================== 市场指数 ====================
function genSparkline(base: number, points = 20): number[] {
  const arr: number[] = [];
  let v = base;
  for (let i = 0; i < points; i++) {
    v += (Math.random() - 0.48) * base * 0.005;
    arr.push(Number(v.toFixed(2)));
  }
  return arr;
}

export const marketIndices: MarketIndex[] = [
  {
    code: "000001.SH",
    name: "上证指数",
    value: 3245.78,
    change: 28.56,
    changePct: 0.89,
    volume: "3856亿",
    sparkline: genSparkline(3245),
  },
  {
    code: "399001.SZ",
    name: "深证成指",
    value: 10582.34,
    change: 125.43,
    changePct: 1.20,
    volume: "4521亿",
    sparkline: genSparkline(10582),
  },
  {
    code: "399006.SZ",
    name: "创业板指",
    value: 2156.89,
    change: -12.34,
    changePct: -0.57,
    volume: "1823亿",
    sparkline: genSparkline(2156),
  },
  {
    code: "000300.SH",
    name: "沪深300",
    value: 3823.45,
    change: 15.67,
    changePct: 0.41,
    volume: "2156亿",
    sparkline: genSparkline(3823),
  },
  {
    code: "000905.SH",
    name: "中证500",
    value: 5234.12,
    change: 8.90,
    changePct: 0.17,
    volume: "1289亿",
    sparkline: genSparkline(5234),
  },
];

// ==================== 持仓 ====================
export const positions: Position[] = [
  {
    code: "600519.SH",
    name: "贵州茅台",
    shares: 100,
    costPrice: 1685.30,
    currentPrice: 1742.56,
    marketValue: 174256.00,
    pnl: 5726.00,
    pnlPct: 3.40,
    weight: 7.65,
    industry: "白酒",
  },
  {
    code: "300750.SZ",
    name: "宁德时代",
    shares: 300,
    costPrice: 182.50,
    currentPrice: 198.34,
    marketValue: 59502.00,
    pnl: 4752.00,
    pnlPct: 8.68,
    weight: 2.61,
    industry: "新能源",
  },
  {
    code: "002594.SZ",
    name: "比亚迪",
    shares: 500,
    costPrice: 235.80,
    currentPrice: 248.90,
    marketValue: 124450.00,
    pnl: 6550.00,
    pnlPct: 5.55,
    weight: 5.46,
    industry: "新能源汽车",
  },
  {
    code: "601318.SH",
    name: "中国平安",
    shares: 2000,
    costPrice: 45.32,
    currentPrice: 48.76,
    marketValue: 97520.00,
    pnl: 6880.00,
    pnlPct: 7.59,
    weight: 4.28,
    industry: "保险",
  },
  {
    code: "000858.SZ",
    name: "五粮液",
    shares: 800,
    costPrice: 142.50,
    currentPrice: 156.30,
    marketValue: 125040.00,
    pnl: 11040.00,
    pnlPct: 9.68,
    weight: 5.49,
    industry: "白酒",
  },
  {
    code: "600036.SH",
    name: "招商银行",
    shares: 5000,
    costPrice: 32.80,
    currentPrice: 35.42,
    marketValue: 177100.00,
    pnl: 13100.00,
    pnlPct: 7.99,
    weight: 7.77,
    industry: "银行",
  },
  {
    code: "601012.SH",
    name: "隆基绿能",
    shares: 2000,
    costPrice: 25.60,
    currentPrice: 23.18,
    marketValue: 46360.00,
    pnl: -4840.00,
    pnlPct: -9.45,
    weight: 2.04,
    industry: "光伏",
  },
  {
    code: "002475.SZ",
    name: "立讯精密",
    shares: 1500,
    costPrice: 38.90,
    currentPrice: 42.15,
    marketValue: 63225.00,
    pnl: 4875.00,
    pnlPct: 8.35,
    weight: 2.78,
    industry: "消费电子",
  },
];

// ==================== 权益曲线 ====================
function genEquityCurve(): { date: string; value: number }[] {
  const data: { date: string; value: number }[] = [];
  const start = new Date("2024-01-02");
  const end = new Date("2025-07-12");
  let value = 2300000;
  const cur = new Date(start);
  while (cur <= end) {
    const dayOfWeek = cur.getDay();
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      value *= 1 + (Math.random() - 0.45) * 0.02;
      data.push({
        date: cur.toISOString().slice(0, 10),
        value: Number(value.toFixed(2)),
      });
    }
    cur.setDate(cur.getDate() + 1);
  }
  return data;
}

export const equityCurve = genEquityCurve();

// ==================== 行业分布 ====================
export const industryDistribution = [
  { name: "白酒", value: 13.14, color: "#3b82f6" },
  { name: "银行", value: 7.77, color: "#60a5fa" },
  { name: "新能源汽车", value: 5.46, color: "#4ade80" },
  { name: "保险", value: 4.28, color: "#86efac" },
  { name: "新能源", value: 2.61, color: "#facc15" },
  { name: "消费电子", value: 2.78, color: "#fde047" },
  { name: "光伏", value: 2.04, color: "#f87171" },
  { name: "现金", value: 19.98, color: "#64748b" },
  { name: "其他", value: 41.94, color: "#475569" },
];

// ==================== 策略列表 ====================
function genStrategyEquity(): { date: string; value: number }[] {
  const data: { date: string; value: number }[] = [];
  const start = new Date("2024-06-01");
  let value = 1000000;
  const cur = new Date(start);
  for (let i = 0; i < 200; i++) {
    if (cur.getDay() !== 0 && cur.getDay() !== 6) {
      value *= 1 + (Math.random() - 0.4) * 0.015;
      data.push({ date: cur.toISOString().slice(0, 10), value: Number(value.toFixed(2)) });
    }
    cur.setDate(cur.getDate() + 1);
  }
  return data;
}

export const strategies: Strategy[] = [
  {
    id: "strat-001",
    name: "AI多因子选股策略",
    type: "量化因子策略",
    status: "running",
    annualizedReturn: 35.2,
    sharpeRatio: 2.8,
    maxDrawdown: 8.3,
    winRate: 72.5,
    totalTrades: 156,
    description: "基于价值、动量、质量、波动率四因子模型，结合AI情绪因子动态调权，每周一调仓",
    equityCurve: genStrategyEquity(),
    createdAt: "2024-06-01",
  },
  {
    id: "strat-002",
    name: "LSTM深度学习预测策略",
    type: "AI预测策略",
    status: "running",
    annualizedReturn: 42.6,
    sharpeRatio: 2.3,
    maxDrawdown: 12.5,
    winRate: 68.3,
    totalTrades: 234,
    description: "LSTM神经网络预测个股5日收益率，结合注意力机制捕捉时序特征",
    equityCurve: genStrategyEquity(),
    createdAt: "2024-08-15",
  },
  {
    id: "strat-003",
    name: "趋势突破策略",
    type: "技术指标策略",
    status: "stopped",
    annualizedReturn: 28.4,
    sharpeRatio: 1.9,
    maxDrawdown: 15.2,
    winRate: 58.7,
    totalTrades: 89,
    description: "基于布林带突破+量能确认的趋势跟踪策略，适合单边行情",
    equityCurve: genStrategyEquity(),
    createdAt: "2024-03-10",
  },
  {
    id: "strat-004",
    name: "量价共振策略",
    type: "技术指标策略",
    status: "running",
    annualizedReturn: 31.8,
    sharpeRatio: 2.5,
    maxDrawdown: 9.6,
    winRate: 65.2,
    totalTrades: 178,
    description: "OBV与MACD共振信号驱动，捕捉量价齐升的主升浪",
    equityCurve: genStrategyEquity(),
    createdAt: "2024-09-20",
  },
  {
    id: "strat-005",
    name: "低波动套利策略",
    type: "量化因子策略",
    status: "backtesting",
    annualizedReturn: 18.5,
    sharpeRatio: 3.1,
    maxDrawdown: 4.2,
    winRate: 78.9,
    totalTrades: 312,
    description: "低波动率因子选股+配对交易，追求稳健绝对收益",
    equityCurve: genStrategyEquity(),
    createdAt: "2025-01-05",
  },
  {
    id: "strat-006",
    name: "动量因子择时策略",
    type: "量化因子策略",
    status: "running",
    annualizedReturn: 26.1,
    sharpeRatio: 2.2,
    maxDrawdown: 11.4,
    winRate: 61.3,
    totalTrades: 142,
    description: "基于20日动量因子的择时策略，动量为正持有、为负空仓，对标 QuantsPlaybook 动量因子研究",
    equityCurve: genStrategyEquity(),
    createdAt: "2025-03-18",
  },
  {
    id: "strat-007",
    name: "反转因子择时策略",
    type: "量化因子策略",
    status: "backtesting",
    annualizedReturn: 19.6,
    sharpeRatio: 2.1,
    maxDrawdown: 9.1,
    winRate: 66.4,
    totalTrades: 176,
    description: "QuantsPlaybook 风格反转因子：近5日超跌(收益<0)持仓，均值回归（真实行情回测）",
    equityCurve: genStrategyEquity(),
    createdAt: "2025-02-18",
  },
  {
    id: "strat-008",
    name: "特质波动率择时策略",
    type: "量化因子策略",
    status: "backtesting",
    annualizedReturn: 16.3,
    sharpeRatio: 2.7,
    maxDrawdown: 5.5,
    winRate: 74.8,
    totalTrades: 142,
    description: "QuantsPlaybook 风格特质波动率因子：低波动regime持仓（真实行情回测）",
    equityCurve: genStrategyEquity(),
    createdAt: "2025-03-02",
  },
  {
    id: "strat-009",
    name: "均线收敛发散择时策略",
    type: "量化因子策略",
    status: "backtesting",
    annualizedReturn: 24.8,
    sharpeRatio: 2.2,
    maxDrawdown: 8.9,
    winRate: 69.1,
    totalTrades: 165,
    description: "QuantsPlaybook 风格均线收敛发散因子：(MA5-MA60)/MA60>0持仓（真实行情回测）",
    equityCurve: genStrategyEquity(),
    createdAt: "2025-03-15",
  },
  {
    id: "strat-010",
    name: "MA双均线交叉基准策略",
    type: "技术指标策略",
    status: "running",
    annualizedReturn: 20.4,
    sharpeRatio: 1.8,
    maxDrawdown: 12.7,
    winRate: 62.0,
    totalTrades: 120,
    description: "MA(5)上穿MA(20)买入、下穿卖出，作为因子择时策略的基准对照（真实行情回测）",
    equityCurve: genStrategyEquity(),
    createdAt: "2025-01-20",
  },
  {
    id: "strat-011",
    name: "ICU均线择时策略",
    type: "技术指标策略",
    status: "backtesting",
    annualizedReturn: 22.1,
    sharpeRatio: 2.0,
    maxDrawdown: 10.3,
    winRate: 66.5,
    totalTrades: 142,
    description: "QuantsPlaybook C-择时类/ICU均线：Siegel重复中位数斜率回归构建ICU均线，收盘价上穿买入、下穿卖出（真实行情回测）",
    equityCurve: genStrategyEquity(),
    createdAt: "2025-04-02",
  },
];

// ==================== 新闻 ====================
export const newsItems: NewsItem[] = [
  {
    id: "news-001",
    title: "央行宣布降准0.5个百分点 释放长期资金约1万亿元",
    source: "新华社",
    time: "10分钟前",
    sentiment: "positive",
    impact: 5,
    relatedStocks: [
      { code: "600036", name: "招商银行" },
      { code: "601318", name: "中国平安" },
    ],
    summary: "央行降准释放流动性，利好银行、保险等金融板块，降低企业融资成本",
  },
  {
    id: "news-002",
    title: "新能源车销量连续6个月同比增长 渗透率突破40%",
    source: "证券时报",
    time: "32分钟前",
    sentiment: "positive",
    impact: 4,
    relatedStocks: [
      { code: "300750", name: "宁德时代" },
      { code: "002594", name: "比亚迪" },
    ],
    summary: "新能源汽车行业持续高景气，产业链上下游受益明显",
  },
  {
    id: "news-003",
    title: "某光伏企业发布业绩预告 净利润同比下降35%",
    source: "财联社",
    time: "1小时前",
    sentiment: "negative",
    impact: -3,
    relatedStocks: [{ code: "601012", name: "隆基绿能" }],
    summary: "光伏行业产能过剩压力持续，硅料价格下跌影响利润",
  },
  {
    id: "news-004",
    title: "消费复苏信号明显 白酒板块集体走强",
    source: "第一财经",
    time: "2小时前",
    sentiment: "positive",
    impact: 4,
    relatedStocks: [
      { code: "600519", name: "贵州茅台" },
      { code: "000858", name: "五粮液" },
    ],
    summary: "端午消费数据回暖，高端白酒批价稳定，渠道库存健康",
  },
  {
    id: "news-005",
    title: "美联储维持利率不变 强调通胀仍处高位",
    source: "Reuters",
    time: "3小时前",
    sentiment: "neutral",
    impact: 0,
    relatedStocks: [],
    summary: "美联储议息会议结果符合预期，对A股影响有限",
  },
  {
    id: "news-006",
    title: "国务院发布促进民营经济发展28条措施",
    source: "人民日报",
    time: "5小时前",
    sentiment: "positive",
    impact: 5,
    relatedStocks: [],
    summary: "政策利好民营经济，提振市场信心，关注科技、消费板块",
  },
];

// ==================== AI研究报告 ====================
export const aiResearchReport: AIResearchReport = {
  date: "2025-07-12",
  marketSummary:
    "今日A股三大指数涨跌不一，上证指数收涨0.89%报3245.78点，深证成指涨1.20%，创业板指微跌0.57%。两市成交额8377亿元，较前一日放量12%。北向资金净流入45.6亿元，连续3日净流入。板块方面，白酒、新能源车板块领涨，光伏板块承压。",
  upReasons: [
    "央行降准释放流动性，市场资金面宽松",
    "消费数据持续回暖，白酒板块强势拉升",
    "北向资金连续净流入，外资看好A股",
    "政策面利好频出，提振市场风险偏好",
  ],
  riskFactors: [
    "美联储维持高利率，外资流向存在不确定性",
    "光伏行业产能过剩，部分个股业绩承压",
    "两市成交量虽放量但仍低于万亿，增量资金有限",
    "中报季临近，部分高估值个股存在业绩证伪风险",
  ],
  focusStocks: [
    {
      code: "600519",
      name: "贵州茅台",
      reason: "高端白酒需求稳健，批价企稳回升，降准利好消费板块",
      risk: "估值处于历史中高位，关注中报业绩兑现",
    },
    {
      code: "300750",
      name: "宁德时代",
      reason: "新能源车销量超预期，动力电池需求旺盛，海外产能加速释放",
      risk: "原材料价格波动，海外政策不确定性",
    },
    {
      code: "002594",
      name: "比亚迪",
      reason: "月度销量持续创新高，海外市场拓展顺利，垂直整合优势明显",
      risk: "行业竞争加剧，价格战影响毛利率",
    },
  ],
  sentimentScore: 72,
  aiJudgment: "bullish",
};

// ==================== 情绪指数趋势 ====================
export const sentimentTrend = Array.from({ length: 30 }, (_, i) => ({
  date: `D-${30 - i}`,
  score: Math.floor(50 + Math.sin(i / 3) * 20 + Math.random() * 10),
}));
