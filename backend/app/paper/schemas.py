"""模拟盘交易系统 — Pydantic 请求/响应模型。

字段命名采用驼峰（camelCase），与前端（Next.js / TypeScript）约定一致。
"""
from pydantic import BaseModel, Field
from typing import Optional


class CreateAccountRequest(BaseModel):
    """创建模拟账户请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="账户名称")
    initialCapital: float = Field(..., gt=0, description="初始资金（元）")
    preset: Optional[str] = Field(None, description="资金预设档位：100万 / 500万 / 1000万 / custom")
    username: str = Field("demo", description="归属用户名（M1 默认 demo）")


class AccountResponse(BaseModel):
    """模拟账户响应（含实时指标）。"""

    id: int
    name: str
    userId: int
    initialCapital: float
    cash: float
    frozenCash: float
    totalAssets: float
    totalPnl: float
    todayPnl: float
    totalPnlPct: float
    positionValue: float
    availableCash: float
    positionRatio: float
    maxDrawdown: float
    sharpeRatio: float
    winRate: float
    profitLossRatio: float
    status: str
    createdAt: str


class AccountMetricsResponse(BaseModel):
    """账户指标响应。"""

    totalAssets: float
    todayPnl: float
    todayPnlPct: float
    totalPnl: float
    totalPnlPct: float
    maxDrawdown: float
    sharpeRatio: float
    winRate: float
    availableCash: float
    positionValue: float
    positionRatio: float
    profitLossRatio: float


class UpdateAccountRequest(BaseModel):
    """更新账户请求。"""

    name: Optional[str] = None
    initialCapital: Optional[float] = None


class AccountOverviewItem(BaseModel):
    """总览中单条账户快照。"""

    id: int
    name: str
    totalAssets: float
    totalPnl: float
    totalPnlPct: float
    positionValue: float
    positionRatio: float
    status: str


class AccountOverviewResponse(BaseModel):
    """全账户汇总。"""

    totalAccounts: int
    totalAssets: float
    totalPnl: float
    totalPnlPct: float
    totalPositionValue: float
    totalCash: float
    activeCount: int
    accounts: list[AccountOverviewItem] = []


# ============================================================
# 行情系统（M2）响应模型
# ============================================================
class QuoteResponse(BaseModel):
    """实时行情（盘口级快照）。"""

    code: str
    name: str
    price: float                       # 最新价（元/股）
    prevClose: float                   # 昨收（元/股）
    open: float                        # 今开（元/股）
    high: float                        # 最高（元/股）
    low: float                         # 最低（元/股）
    volume: float                      # 成交量（手）
    amount: float                      # 成交额（元）
    turnover: float                    # 换手率（%）
    amplitude: float                   # 振幅（%）
    change: float                      # 涨跌额（元）
    changePct: float                   # 涨跌幅（%）
    time: str                          # 行情时间（ISO）
    dataSource: str                    # akshare / mock


class OrderBookLevel(BaseModel):
    """五档盘口单档。"""

    price: float
    volume: float                      # 挂单量（手）


class OrderBookResponse(BaseModel):
    """五档行情（买一~买五，卖一~卖五）。"""

    code: str
    name: str
    bids: list[OrderBookLevel]         # 买一~买五（price 高→低）
    asks: list[OrderBookLevel]         # 卖一~卖五（price 低→高）
    time: str
    dataSource: str


class KlinePoint(BaseModel):
    """单根 K 线。"""

    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float


class KlineResponse(BaseModel):
    """K 线序列。"""

    code: str
    name: str
    period: str                        # 1m/5m/15m/30m/60m/day/week/month
    points: list[KlinePoint]
    dataSource: str


class CapitalFlowResponse(BaseModel):
    """资金流向。"""

    code: str
    name: str
    mainInflow: float                  # 主力净流入（元）
    netInflow: float                   # 净特大单+大单（元）
    superLarge: float                  # 超大单净流入（元）
    large: float                       # 大单净流入（元）
    medium: float                      # 中单净流入（元）
    small: float                       # 小单净流入（元）
    time: str
    dataSource: str


class SectorResponse(BaseModel):
    """行业 / 概念板块。"""

    code: str
    name: str
    changePct: float
    leader: str                        # 领涨股名称
    leaderCode: str
    dataSource: str


class DataSourceStatus(BaseModel):
    """数据源状态。"""

    akshareAvailable: bool             # akshare 模块是否已安装
    networkReachable: bool             # 主行情接口实时探测是否可达
    mode: str                          # real / mock（模块可用且网络可达 → real）
    cacheEntries: int
    note: str = ""                     # 提示：以各接口 dataSource 字段为准


# ============================================================
# 订单系统（M3）请求/响应模型
# ============================================================
class CreateOrderRequest(BaseModel):
    """创建订单请求。

    orderType:
        limit       限价单
        market      市价单
        stop_profit 止盈单（卖出条件单，price 升至 triggerPrice 触发）
        stop_loss   止损单（卖出条件单，price 跌至 triggerPrice 触发）
        grid        网格单（按 grid* 参数生成多笔子限价单）
        ai          AI 自动单（由 M7 决策，撮合同 limit/market）
    direction: buy / sell
    tranches: 分批建仓/减仓笔数（>1 时分批）
    """

    accountId: int
    code: str
    name: str = ""
    direction: str                    # buy / sell
    orderType: str = "limit"          # limit/market/stop_profit/stop_loss/grid/ai
    price: float = 0.0                # 委托价（市价单可留 0）
    quantity: int                     # 委托数量（股，100 的整数倍）
    triggerPrice: float = 0.0         # 止盈/止损触发价
    tranches: int = 1                 # 分批笔数
    gridUpper: float = 0.0            # 网格上沿
    gridLower: float = 0.0            # 网格下沿
    gridStep: float = 0.0             # 网格步长
    gridQtyPer: int = 0               # 每格数量（股）
    source: str = "human"             # human / ai
    remark: str = ""
    params: Optional[dict] = None      # M7：AI 下单附参（如止损/止盈价，透传给 OrderService）


class OrderResponse(BaseModel):
    """订单响应。"""

    id: int
    accountId: int
    code: str
    name: str
    direction: str
    orderType: str
    price: float
    quantity: int
    filledQuantity: int
    avgFillPrice: float
    amount: float
    fee: float
    status: str                       # pending/partial/filled/cancelled/expired
    source: str
    triggerPrice: float
    parentId: int
    createdAt: str
    updatedAt: str


class PositionResponse(BaseModel):
    """持仓响应。"""

    accountId: int
    code: str
    name: str
    industry: str
    shares: int
    sellableShares: int               # 可卖数量（T+1）
    costPrice: float                  # 成本价（移动平均）
    buyPrice: float                   # 首笔买入价
    currentPrice: float
    marketValue: float
    pnlAmount: float
    pnlPct: float
    holdDays: int
    positionRatio: float              # 仓位比例(%)
    stopLossPrice: float = 0.0        # 止损价（M7 AI 自动交易回写）
    takeProfitPrice: float = 0.0      # 止盈价（M7 AI 自动交易回写）


class PositionSummary(BaseModel):
    """持仓汇总（M4：盈亏分析 / 集中度 / 行业分布）。"""

    accountId: int
    positionCount: int                # 持仓标的数
    totalMarketValue: float           # 持仓总市值
    totalCost: float                  # 持仓总成本（移动加权）
    unrealizedPnl: float              # 浮动盈亏（元）
    unrealizedPnlPct: float           # 浮动盈亏率(%)
    realizedPnl: float                # 累计已实现盈亏（元，来自成交记录）
    todayPnl: float                   # 当日浮动盈亏（元，基于昨收）
    todayPnlPct: float                # 当日盈亏率(%)
    totalPnl: float                   # 总盈亏 = 浮动 + 已实现（元）
    maxPositionRatio: float           # 最大单一持仓占比(%)
    top3Ratio: float                  # 前三大持仓合计占比(%)
    industryDistribution: list[dict]  # 行业分布 [{industry, marketValue, ratio}]


# ====================== M5 风险控制 ======================
class RiskConfigRequest(BaseModel):
    """风险参数配置请求（比例型为 0-1 小数，金额为元）。"""

    enabled: bool = True
    maxPositionRatio: float = Field(0.5, ge=0.0, le=1.0)          # 单票最大仓位占比
    maxTotalPositionRatio: float = Field(0.9, ge=0.0, le=1.0)      # 总仓位上限
    maxSingleAmount: float = Field(500000.0, ge=0.0)               # 单笔最大委托金额(元)
    maxDailyLoss: float = Field(50000.0, ge=0.0)                   # 单日最大亏损(元)
    stopLossRatio: float = Field(0.20, ge=0.0, le=1.0)             # 个股止损线
    allowShort: bool = False


class RiskConfigResponse(BaseModel):
    """风险参数配置响应。"""

    accountId: int
    enabled: bool
    maxPositionRatio: float
    maxTotalPositionRatio: float
    maxSingleAmount: float
    maxDailyLoss: float
    stopLossRatio: float
    allowShort: bool


class RiskMetrics(BaseModel):
    """实时风险指标（M5）。所有占比为 0-1 小数；status 为 ok/warn/breach。"""

    accountId: int
    totalAssets: float                 # 账户总资产(元)
    positionValue: float               # 持仓总市值(元)
    totalPositionRatio: float          # 当前总仓位(0-1)
    maxPositionRatio: float            # 当前最大单票仓位(0-1)
    todayPnl: float                    # 当日盈亏(元)
    dailyLoss: float                   # 今日亏损绝对值(元)
    dailyLossRatio: float              # 今日亏损 / 单日上限(0-1)
    concentrationStatus: str           # 单票/总仓位状态
    stopLossStatus: str                # 个股止损状态
    dailyLossStatus: str               # 单日亏损状态
    overallStatus: str                 # 综合风险状态
    breaches: list[str]                # 当前触发项说明
    configSnapshot: dict               # 生效的风控参数快照


class RiskEventResponse(BaseModel):
    """风险事件响应。"""

    id: int
    accountId: int
    code: str
    eventType: str
    level: str
    message: str
    detail: dict
    acked: bool
    createdAt: str


# ====================== 智能风控中心（risk center 增强） ======================
class RiskRuleRequest(BaseModel):
    """创建/更新风控规则请求。

    ruleType 可选：SECTOR_CONCENTRATION / MAX_DRAWDOWN / LEVERAGE /
    BLACKLIST / OVERNIGHT_LIMIT / CUSTOM；
    detail 为结构化参数（如黑名单 detail={"codes":["600519","000858"]}）。
    """

    name: str = Field(..., min_length=1, max_length=100, description="规则名称")
    ruleType: str = Field(..., description="规则类型枚举")
    threshold: float = 0.0                                   # 数值阈值（多为百分比）
    scope: str = "account"                                  # account / global
    enabled: bool = True
    severity: str = "warn"                                  # warn / high / critical
    detail: Optional[dict] = None                           # 结构化参数（黑名单代码等）


class RiskRuleResponse(BaseModel):
    """风控规则响应。"""

    id: int
    accountId: Optional[int] = None
    name: str
    ruleType: str
    threshold: float
    scope: str
    enabled: bool
    severity: str
    detail: dict = {}
    createdAt: str
    updatedAt: str


class RiskReportResponse(BaseModel):
    """智能风控报告响应（确定性算法生成，不依赖外部 LLM）。"""

    accountId: int
    generatedAt: str
    overallStatus: str                 # ok / warn / breach
    score: float                       # 风险评分 0-100（越高越危险）
    summary: str                       # 概览叙述
    metrics: dict                      # 关键指标快照（同 RiskMetrics）
    activeRules: int                   # 启用规则数
    triggeredRules: list[dict]         # 触发规则 [{ruleId,name,ruleType,severity,message}]
    topBreaches: list[str]             # 当前指标突破项
    suggestions: list[str]             # 处置建议


# ====================== M6 资金与收益曲线 / 统计中心 ======================
class EquityPoint(BaseModel):
    """日级权益快照点（收益曲线的基本单元）。"""

    date: str                               # YYYY-MM-DD
    totalAssets: float                     # 总资产（元）
    cash: float                            # 现金（元）
    positionValue: float                   # 持仓市值（元）
    dailyPnl: float                        # 当日盈亏（元）
    dailyPnlPct: float                     # 当日盈亏率(%)
    cumulativePnl: float                   # 累计盈亏（元）
    cumulativePnlPct: float                # 累计收益率(%)


class AccountStatistics(BaseModel):
    """账户统计中心（M6）：由权益快照序列 + 平仓成交记录联合驱动。"""

    accountId: int
    initialCapital: float                  # 初始资金（元）
    currentAssets: float                   # 当前总资产（元，取最新快照）
    cumulativePnl: float                   # 累计盈亏（元）
    cumulativePnlPct: float                # 累计收益率(%)
    totalReturn: float                     # 总收益率(%) = cumulativePnlPct
    annualizedReturn: float                # 年化收益率(%)（首末快照日历跨度）
    maxDrawdown: float                     # 最大回撤(%)（基于权益序列）
    sharpeRatio: float                     # 夏普比率（年化，无风险利率取 0）
    winRate: float                         # 胜率(%)（盈利平仓数/平仓总数）
    profitLossRatio: float                # 盈亏比（平均盈利/平均亏损，无亏损时为 0）
    tradeCount: int                        # 平仓交易笔数（每笔卖出成交）
    winCount: int                          # 盈利平仓数
    lossCount: int                         # 亏损平仓数
    avgWin: float                          # 平均盈利（元）
    avgLoss: float                         # 平均亏损（元，正数表示亏损额）
    snapshotCount: int                     # 快照数量（收益曲线点数）


# ====================== M7 AI 自动交易 ======================
class PaperStrategyConfig(BaseModel):
    """AI 交易策略配置（PaperStrategy 表）。"""

    id: str
    accountId: int
    name: str
    description: str = ""
    enabled: bool = False
    params: dict = {}                  # 策略参数（监控标的 / 仓位 / 止损止盈等）
    metrics: dict = {}                 # 最新绩效快照
    createdAt: str
    updatedAt: str


class PaperSignal(BaseModel):
    """交易信号（Signal 表）。"""

    id: int
    accountId: int
    code: str
    name: str
    signalType: str                   # buy / sell / hold
    strength: float                   # 强度(0-100)
    source: str                       # ai / rule
    reason: str = ""
    priceTarget: float = 0.0
    stopLoss: float = 0.0
    takeProfit: float = 0.0
    riskScore: float = 0.0
    createdAt: str


class PaperAILog(BaseModel):
    """AI 决策 / 交易日志（TradeLog 表，log_type=ai_decision/ai_trade）。"""

    id: int
    accountId: int
    logType: str
    level: str
    message: str
    meta: dict = {}
    createdAt: str


class PaperAutoStatus(BaseModel):
    """AI 自动交易运行状态。"""

    accountId: int
    enabledStrategies: int             # 当前启用策略数
    running: bool                      # 后台循环是否在处理该账户
    lastRunAt: str = ""                # 最近一次运行时间（ISO）
    lastRunSummary: dict = {}          # 最近一次运行摘要（信号数 / 下单数 / 触发数）
    dataSource: str = ""               # 行情数据源（akshare/mock）
    watchedCodes: int = 0              # 本轮监控标的数


class PaperHoldingSLTP(BaseModel):
    """持仓止损/止盈设置（含派生字段，供前端面板展示/编辑）。"""

    accountId: int
    code: str
    name: str
    shares: int
    costPrice: float
    currentPrice: float
    stopLossPrice: float = 0.0
    takeProfitPrice: float = 0.0


# ====================== M8 回测模块 ======================
class RunBacktestRequest(BaseModel):
    """运行一次回测的请求。复用主平台 backtest_engine（均线交叉 / 因子择时）。"""

    strategy: str = "均线交叉(MA5/MA20)"          # 策略名称/类型
    stockPool: str = "沪深300"                    # 股票池（映射标的）
    code: Optional[str] = None                    # 指定标的（优先于 stockPool）
    startDate: str = ""                           # 回测起始 YYYY-MM-DD（空=取足够长历史）
    endDate: str = ""                             # 回测结束 YYYY-MM-DD
    initialCapital: float = 1_000_000.0           # 初始资金（元）
    accountId: Optional[int] = None               # 关联模拟盘账户（可选）
    strategyId: Optional[str] = None              # 关联 AI 策略（可选，回测后可用于部署）


class BacktestRunResponse(BaseModel):
    """回测记录响应（backtest_runs 表 + 完整结果）。"""

    id: int
    accountId: Optional[int] = None
    strategyName: str = ""
    symbol: str = ""
    startDate: str = ""
    endDate: str = ""
    initialCapital: float = 0.0
    totalReturn: float = 0.0                       # 总收益率(%)
    annualizedReturn: float = 0.0                  # 年化收益率(%)
    sharpeRatio: float = 0.0
    maxDrawdown: float = 0.0                        # 最大回撤(%)
    calmarRatio: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    winRate: float = 0.0                            # 胜率(%)
    totalTrades: int = 0
    equityCurve: list = []                          # list[{date,value}]
    trades: list = []                               # list[dict]
    dataSource: str = ""
    params: dict = {}
    mode: str = "factor"                            # factor（因子/均线）/ event（事件驱动）
    createdAt: str = ""


class BacktestStrategyOption(BaseModel):
    """可选策略类型（供前端下拉）。"""

    key: str
    label: str
    pnlPct: float = 0.0


# ====================== M181 事件驱动回测引擎 ======================
class EventRule(BaseModel):
    """一条事件规则：side 决定入场/出场，kind 决定触发条件，params 为条件参数。"""

    side: str = "entry"                  # entry（入场）/ exit（出场）
    kind: str = "ma_cross"               # ma_cross / price_breakout / rsi / drawdown_stop / take_profit / hold_days
    params: dict = {}                    # 条件参数（如 {"fast":5,"slow":20} / {"window":20} / {"pct":8.0}）


class RunEventBacktestRequest(BaseModel):
    """运行一次事件驱动回测的请求。"""

    strategyName: str = "事件驱动组合"                 # 策略展示名
    universe: list = []                              # 标的代码列表（如 ["sh600519","sz000858"]）
    stockPool: str = ""                             # 股票池（便捷入口，可选；与 universe 二选一）
    code: Optional[str] = None                      # 单个标的（便捷入口，可选）
    startDate: str = ""                             # 回测起始 YYYY-MM-DD（空=取足够长历史）
    endDate: str = ""                               # 回测结束 YYYY-MM-DD
    initialCapital: float = 1_000_000.0             # 初始资金（元）
    rules: list = []                                # 事件规则列表（EventRule 结构）
    risk: dict = {}                                 # 全局风控 {"stopLoss":8.0,"takeProfit":20.0}
    accountId: Optional[int] = None                 # 关联模拟盘账户（可选）
    strategyId: Optional[str] = None                # 关联 AI 策略（可选）


class BacktestEventStrategy(BaseModel):
    """事件驱动策略模板（供前端下拉与规则预设）。"""

    key: str
    label: str
    rules: list = []                                # 预置的事件规则列表
    risk: dict = {}                                 # 预置风控


# ============================================================
# M179 股票池自动维护
# ============================================================
class PoolItemRequest(BaseModel):
    """新增股票池标的请求。"""

    code: str = Field(..., min_length=1, max_length=20, description="股票代码（6 位）")
    name: str = ""
    category: str = ""
    note: str = ""
    pinned: bool = False
    source: str = "manual"                          # manual / sync:板块名


class PoolItemResponse(BaseModel):
    """股票池标的响应。"""

    id: int
    accountId: int
    code: str
    name: str
    category: str
    note: str
    pinned: bool
    health: str                                    # unknown/ok/suspended/st/illiquid
    source: str
    lastChecked: Optional[str] = None
    createdAt: str


class PoolItemUpdateRequest(BaseModel):
    """更新股票池标的（均可选，仅传需修改字段）。"""

    category: Optional[str] = None
    note: Optional[str] = None
    pinned: Optional[bool] = None


class PoolConfigRequest(BaseModel):
    """股票池自动维护配置请求。"""

    autoSync: bool = False
    syncSource: str = "manual"                      # manual / sector / concept / index
    syncName: str = ""                             # 跟踪的板块 / 指数名称
    removeSuspended: bool = True
    removeSt: bool = True
    removeIlliquid: bool = False
    minTurnover: float = 1.0                       # 最小换手率(%)阈值
    maxSize: int = 0                               # 池容量上限，0=不限


class PoolConfigResponse(BaseModel):
    """股票池自动维护配置响应。"""

    accountId: int
    autoSync: bool
    syncSource: str
    syncName: str
    removeSuspended: bool
    removeSt: bool
    removeIlliquid: bool
    minTurnover: float
    maxSize: int
    updatedAt: Optional[str] = None


class PoolChangeLogResponse(BaseModel):
    """股票池变更日志响应。"""

    id: int
    accountId: int
    code: str
    name: str
    action: str                                    # add / remove
    reason: str
    source: str
    createdAt: str


class PoolMaintainResult(BaseModel):
    """手动触发维护的结果。"""

    accountId: int
    checked: int = 0
    added: int = 0
    removed: int = 0
    skippedPinned: int = 0
    details: list = []


# ============================================================
# 研究员 Agent（#182：自动挖掘因子、生成策略）
# ============================================================
class PaperFactorFindingResponse(BaseModel):
    """研究员挖掘出的因子结论响应。"""

    id: int
    sessionId: int
    name: str
    factorType: str                                # momentum/volatility/reversal/rsi/volume/quality
    description: str
    direction: str                                 # long / short / neutral
    score: float                                   # 因子强度评分(0-100)
    detail: dict = {}
    createdAt: str


class PaperStrategyIdeaResponse(BaseModel):
    """研究员生成的策略想法响应（规则兼容事件驱动回测引擎）。"""

    id: int
    sessionId: int
    accountId: Optional[int] = None
    name: str
    description: str
    universe: list = []
    entryRules: list = []                          # EventRule 列表
    exitRules: list = []                           # EventRule 列表
    risk: dict = {}                                # {stopLoss, takeProfit}
    logic: str
    expected: str
    backtestRunId: Optional[int] = None
    backtested: bool = False
    createdAt: str


class PaperResearchSessionResponse(BaseModel):
    """研究员一次研究会话响应（含因子结论与策略想法）。"""

    id: int
    accountId: Optional[int] = None
    universe: list = []
    mode: str                                      # rule / llm
    model: str
    summary: str
    status: str
    factors: list = []                             # PaperFactorFindingResponse 列表
    ideas: list = []                               # PaperStrategyIdeaResponse 列表
    createdAt: str


class RunResearchRequest(BaseModel):
    """触发一次研究员 Agent 研究的请求。"""

    accountId: Optional[int] = None
    universe: list = []                             # 研究标的列表（代码）；空则用默认观察池
    useLlm: bool = False                           # 是否启用大模型生成（否则规则确定性）
    maxIdeas: int = 3                              # 最多生成策略想法数


class RunResearchResponse(BaseModel):
    """触发研究的返回。"""

    session: PaperResearchSessionResponse
    factorCount: int = 0
    ideaCount: int = 0


# ====================== 策略市场 (Marketplace, #183) ======================


class PublishStrategyRequest(BaseModel):
    """发布策略到市场的请求。"""

    accountId: int
    name: str
    description: str = ""
    sourceType: str = "manual"                      # manual / backtest / idea
    sourceId: Optional[int] = None
    entryRules: list = []
    exitRules: list = []
    risk: dict = {}
    universe: list = []
    logic: str = ""
    performanceSnapshot: dict = {}
    tags: list = []


class PublishedStrategyResponse(BaseModel):
    """策略市场中一条已发布的策略。"""

    id: int
    authorAccountId: int
    name: str
    description: str
    sourceType: str
    sourceId: Optional[int] = None
    entryRules: list = []
    exitRules: list = []
    risk: dict = {}
    universe: list = []
    logic: str
    performanceSnapshot: dict = {}
    tags: list = []
    version: int
    isPublished: bool
    createdAt: str
    updatedAt: str


class StrategyMarketplaceListing(BaseModel):
    """市场浏览的一条策略（含聚合统计）。"""

    id: int
    authorAccountId: int
    name: str
    description: str
    sourceType: str
    tags: list = []
    isPublished: bool
    avgRating: float = 0.0
    ratingCount: int = 0
    subscriberCount: int = 0
    performanceSnapshot: dict = {}
    createdAt: str


class SubscribeRequest(BaseModel):
    """订阅策略的请求。"""

    accountId: int
    publishedStrategyId: int


class StrategyRatingRequest(BaseModel):
    """评分/评价的请求。"""

    accountId: int
    publishedStrategyId: int
    score: int = 5                                  # 1-5
    review: str = ""


class StrategyRatingResponse(BaseModel):
    """一条评分/评价。"""

    id: int
    accountId: int
    publishedStrategyId: int
    score: int
    review: str
    createdAt: str


class MarketplaceLeaderboardEntry(BaseModel):
    """排行榜条目。"""

    publishedStrategyId: int
    name: str
    authorAccountId: int
    avgRating: float = 0.0
    ratingCount: int = 0
    subscriberCount: int = 0
    compositeScore: float = 0.0                      # 综合评分排序


# ====================== 策略组合 (Portfolio, #184) ======================


class PortfolioAllocation(BaseModel):
    """单条分配。"""

    strategyId: str                                   # PaperStrategy.id (UUID)
    weight: float = 0.0                              # 资金分配比例 (%)


class PortfolioRequest(BaseModel):
    """创建/更新组合的请求。"""

    accountId: int
    name: str
    description: str = ""
    allocation: list[PortfolioAllocation] = []        # 策略分配列表
    totalCapital: float = 0.0
    enabled: bool = True


class PortfolioResponse(BaseModel):
    """组合响应。"""

    id: int
    accountId: int
    name: str
    description: str
    allocation: list[PortfolioAllocation] = []
    totalCapital: float = 0.0
    enabled: bool
    strategyCount: int = 0
    createdAt: str
    updatedAt: str


class PortfolioRebalanceResponse(BaseModel):
    """再平衡响应。"""

    id: int
    portfolioId: int
    triggeredAt: str
    reason: str
    allocationsBefore: list = []
    allocationsAfter: list = []
    status: str
    notes: str


class DailyReviewResponse(BaseModel):
    """每日复盘报告响应。"""

    id: int
    accountId: int
    date: str
    summary: str
    tradesSummary: dict = {}
    marketSummary: str = ""
    pnlSummary: dict = {}
    performance: dict = {}
    decisions: list = []
    generatedBy: str = "rule"
    createdAt: str


class DailyReviewGenerateRequest(BaseModel):
    """手动触发复盘的请求。"""

    accountId: int
