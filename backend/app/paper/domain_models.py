"""模拟盘交易系统 — 领域模型（ORM）。

本模块定义模拟盘交易所需的全部数据表（ER）：
    users           用户
    paper_accounts  模拟账户
    paper_positions 持仓
    paper_orders    订单
    paper_trades    成交
    signals         信号
    paper_strategies 交易策略（AI 自动交易）
    watchlists      自选股
    backtest_runs   回测记录
    trade_logs      日志
    notifications   通知

设计约束（与平台既有一致）：
- 仅使用 SQLAlchemy 跨库可移植类型（String/Integer/Float/DateTime/JSON/...），
  不使用 ARRAY / PG Enum 等专有类型，保证 SQLite 与 PostgreSQL 通用。
- JSON 列用 sqlalchemy.JSON（SQLite / PostgreSQL 均原生支持）。
- 金额单位为「元」，价格为「元/股」，数量为「股」。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.db.database import Base


class User(Base):
    """用户表（模拟盘账户归属）。

    说明：M1 仅建立最小用户模型，登录鉴权（/login）在后续模块实现；
    当前账户创建默认挂在 demo 用户下。
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    nickname = Column(String(64), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PaperAccount(Base):
    """模拟账户表。

    账户核心指标（总资产/收益/回撤/夏普/胜率/盈亏比等）实时由服务层计算，
    部分历史型指标（max_drawdown/sharpe_ratio/win_rate/profit_loss_ratio）
    在 M6 收益曲线与统计中心落地后由快照驱动，M1 先以 0 占位。
    """

    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=True)       # 关联 users.id
    name = Column(String(100), nullable=False)                 # 账户名称
    # —— 资金 ——
    initial_capital = Column(Float, default=1_000_000.0)       # 初始资金（元）
    cash = Column(Float, default=1_000_000.0)                  # 现金（元）
    frozen_cash = Column(Float, default=0.0)                   # 冻结资金（元）
    # —— 实时派生指标（服务层写回，便于查询） ——
    total_assets = Column(Float, default=1_000_000.0)          # 总资产（元）
    position_value = Column(Float, default=0.0)                # 持仓市值（元）
    available_cash = Column(Float, default=1_000_000.0)        # 可用资金（元）
    position_ratio = Column(Float, default=0.0)                # 仓位比例(0-100)
    total_pnl = Column(Float, default=0.0)                     # 总收益（元）
    total_pnl_pct = Column(Float, default=0.0)                 # 累计收益率(%)
    today_pnl = Column(Float, default=0.0)                     # 今日收益（元）
    # —— 风险/绩效指标（M6 前为 0 占位） ——
    max_drawdown = Column(Float, default=0.0)                  # 最大回撤(%)
    sharpe_ratio = Column(Float, default=0.0)                  # 夏普比率
    win_rate = Column(Float, default=0.0)                      # 胜率(%)
    profit_loss_ratio = Column(Float, default=0.0)             # 盈亏比
    # —— 状态 ——
    status = Column(String(20), default="active")              # active / closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperPosition(Base):
    """持仓表。"""

    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "code", name="uq_paper_pos_account_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    code = Column(String(20), nullable=False, index=True)      # 股票代码
    name = Column(String(50), default="")                      # 股票名称
    industry = Column(String(50), default="")                  # 行业
    shares = Column(Integer, default=0)                        # 持仓数量（股）
    sellable_shares = Column(Integer, default=0)               # 可卖数量（股，T+1）
    cost_price = Column(Float, default=0.0)                    # 成本价（元/股，移动平均）
    buy_price = Column(Float, default=0.0)                     # 买入价格（首笔，元/股）
    current_price = Column(Float, default=0.0)                 # 当前价格（元/股，快照）
    market_value = Column(Float, default=0.0)                  # 市值（元）
    pnl_amount = Column(Float, default=0.0)                    # 盈亏金额（元）
    pnl_pct = Column(Float, default=0.0)                        # 盈亏比例(%)
    hold_days = Column(Integer, default=0)                     # 持仓天数
    position_ratio = Column(Float, default=0.0)                # 仓位比例(0-100)
    # —— M7：AI 自动交易止损/止盈回写（0 表示未设置）——
    stop_loss_price = Column(Float, default=0.0)              # 止损价（元/股）
    take_profit_price = Column(Float, default=0.0)            # 止盈价（元/股）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperOrder(Base):
    """订单表。

    订单状态 status：
        pending    待成交
        partial    部分成交
        filled     已成交
        cancelled  已撤单
        expired    已失效
    订单类型 order_type：
        limit       限价单
        market      市价单
        stop_profit 止盈单
        stop_loss   止损单
        grid        网格单
        ai          AI 自动单
    来源 source：human / ai
    """

    __tablename__ = "paper_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(50), default="")
    direction = Column(String(10), nullable=False)            # buy / sell
    order_type = Column(String(20), default="limit")          # 见上
    price = Column(Float, default=0.0)                         # 委托价格（元/股）
    quantity = Column(Integer, default=0)                       # 委托数量（股）
    filled_quantity = Column(Integer, default=0)               # 已成交数量（股）
    avg_fill_price = Column(Float, default=0.0)                # 成交均价（元/股）
    amount = Column(Float, default=0.0)                         # 委托金额（元）
    fee = Column(Float, default=0.0)                             # 手续费合计（元）
    status = Column(String(20), default="pending")             # 见上
    source = Column(String(10), default="human")               # human / ai
    # —— 扩展字段（M3：分批/网格/条件单）——
    parent_id = Column(Integer, default=0, index=True)         # 父订单 id（分批/网格子单）
    trigger_price = Column(Float, default=0.0)                 # 触发价（止盈/止损）
    params = Column(JSON)                                      # 网格/分批参数
    remark = Column(String(200), default="")                   # 备注
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperTrade(Base):
    """成交表（每笔撮合成功记录一笔）。"""

    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    order_id = Column(Integer, index=True, nullable=True)      # 关联 paper_orders.id
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(50), default="")
    direction = Column(String(10), nullable=False)             # buy / sell
    price = Column(Float, default=0.0)                          # 成交价格（元/股）
    quantity = Column(Integer, default=0)                        # 成交数量（股）
    amount = Column(Float, default=0.0)                          # 成交金额（元）
    fee = Column(Float, default=0.0)                             # 手续费（元）
    realized_pnl = Column(Float, default=0.0)                   # 实现盈亏（卖出时，元）
    trade_time = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Signal(Base):
    """信号表（AI 或规则生成）。"""

    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=True)
    code = Column(String(20), index=True)
    name = Column(String(50), default="")
    signal_type = Column(String(10), default="buy")            # buy / sell / hold
    strength = Column(Float, default=0.0)                       # 强度(0-100)
    source = Column(String(10), default="ai")                  # ai / rule
    reason = Column(Text, default="")                           # 买入/卖出理由
    price_target = Column(Float, default=0.0)                  # 目标价格
    stop_loss = Column(Float, default=0.0)                      # 止损价格
    take_profit = Column(Float, default=0.0)                    # 止盈价格
    risk_score = Column(Float, default=0.0)                    # 风险评分
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PaperStrategy(Base):
    """交易策略表（AI 自动交易策略配置）。

    与既有的 analytics `strategies` 表区分：本表面向「可自动下单」的交易策略。
    """

    __tablename__ = "paper_strategies"

    id = Column(String(50), primary_key=True)
    account_id = Column(Integer, index=True, nullable=True)
    name = Column(String(100), default="")
    description = Column(Text, default="")
    enabled = Column(Boolean, default=False)                   # 是否启用 AI 自动交易
    params = Column(JSON)                                      # 策略参数
    metrics = Column(JSON)                                      # 最新绩效
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Watchlist(Base):
    """自选股（股票池）表。

    M179 股票池自动维护扩展字段：
    - pinned：锁定标的，自动维护不会将其移除；
    - category：分组 / 标签（如「核心仓」「观察」）；
    - health：健康状态（unknown/ok/suspended/st/illiquid），由后台循环检测回写；
    - last_checked：最近一次健康检测时间；
    - source：来源（manual / sync:板块名），标识该标的如何进入股票池。
    """

    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("account_id", "code", name="uq_watchlist_account_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(50), default="")
    note = Column(String(200), default="")
    # —— M179 股票池自动维护扩展字段 ——
    pinned = Column(Boolean, default=False, nullable=False)        # 锁定，不被自动移除
    category = Column(String(30), default="", nullable=False)      # 分组 / 标签
    health = Column(String(20), default="unknown", nullable=False)  # unknown/ok/suspended/st/illiquid
    last_checked = Column(DateTime, nullable=True)                 # 最近健康检测时间
    source = Column(String(30), default="manual", nullable=False)  # manual / sync:板块名
    created_at = Column(DateTime, default=datetime.utcnow)


class PaperPoolConfig(Base):
    """股票池自动维护配置（每个账户一条）。"""

    __tablename__ = "paper_pool_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, unique=True, nullable=False)
    auto_sync = Column(Boolean, default=False, nullable=False)      # 是否从板块自动同步成分
    sync_source = Column(String(20), default="manual", nullable=False)  # manual/sector/concept/index
    sync_name = Column(String(50), default="", nullable=False)      # 跟踪的板块 / 指数名称
    remove_suspended = Column(Boolean, default=True, nullable=False)  # 自动移除停牌
    remove_st = Column(Boolean, default=True, nullable=False)         # 自动移除 ST / *ST
    remove_illiquid = Column(Boolean, default=False, nullable=False)  # 自动移除流动性不足
    min_turnover = Column(Float, default=1.0, nullable=False)         # 最小换手率(%)阈值
    max_size = Column(Integer, default=0, nullable=False)             # 池容量上限，0=不限
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperPoolChangeLog(Base):
    """股票池变更日志（自动同步新增 / 自动移除均留痕）。"""

    __tablename__ = "paper_pool_changelog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    code = Column(String(20), index=True, default="")
    name = Column(String(50), default="")
    action = Column(String(10), default="add", nullable=False)   # add / remove
    reason = Column(String(100), default="", nullable=False)     # 触发原因
    source = Column(String(30), default="manual", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class BacktestRun(Base):
    """回测记录表。"""

    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=True)
    strategy_name = Column(String(100), default="")
    symbol = Column(String(20), index=True)
    start_date = Column(String(20), default="")
    end_date = Column(String(20), default="")
    initial_capital = Column(Float, default=0.0)
    total_return = Column(Float, default=0.0)
    annualized_return = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    calmar_ratio = Column(Float, default=0.0)                  # Calmar 比率
    alpha = Column(Float, default=0.0)
    beta = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    equity_curve = Column(JSON)                                # list[{date,value}]
    trades = Column(JSON)                                      # list[dict]
    data_source = Column(String(20), default="")                   # westock / mock / event-engine
    params = Column(JSON, default=dict)                             # 回测请求配置（策略/标的/区间/资金）
    mode = Column(String(20), default="factor")                    # factor（因子/均线）/ event（事件驱动）
    created_at = Column(DateTime, default=datetime.utcnow)


class TradeLog(Base):
    """日志表（AI 决策 / 交易 / 异常 / 接口 / 用户操作）。"""

    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=True)
    log_type = Column(String(20), default="info")              # ai_decision/trade/exception/api/user_action
    level = Column(String(10), default="info")                 # info / warn / error
    message = Column(Text, default="")
    meta = Column(JSON)                                        # 结构化附加信息
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Notification(Base):
    """通知表（买卖 / AI 信号 / 止盈 / 止损 / 公告提醒；渠道含微信/企业微信/Telegram/邮件）。"""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=True)
    channel = Column(String(20), default="in_app")             # in_app/wechat/wecom/telegram/email
    notify_type = Column(String(20), default="signal")         # buy/sell/ai_signal/take_profit/stop_loss/announcement
    title = Column(String(200), default="")
    message = Column(Text, default="")
    is_read = Column(Boolean, default=False)
    is_sent = Column(Boolean, default=False)                   # 外部渠道是否已发送
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PaperRiskConfig(Base):
    """风险参数配置表（M5：前置风控阈值，按账户维度）。

    所有比例型参数为 0-1 小数（如 0.5 表示 50%）；
    金额单位为「元」。未配置时由 RiskService 返回平台默认值。
    """

    __tablename__ = "paper_risk_configs"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_paper_risk_account"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)   # 关联 paper_accounts.id
    enabled = Column(Boolean, default=True)                    # 风控总开关
    max_position_ratio = Column(Float, default=0.5)             # 单票最大仓位占比(0-1)
    max_total_position_ratio = Column(Float, default=0.9)       # 总仓位上限(0-1)
    max_single_amount = Column(Float, default=500000.0)         # 单笔最大委托金额(元)
    max_daily_loss = Column(Float, default=50000.0)            # 单日最大亏损(元)
    stop_loss_ratio = Column(Float, default=0.20)              # 个股止损线(0-1)，浮亏超此比例预警
    allow_short = Column(Boolean, default=False)                # 是否允许卖空
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperRiskEvent(Base):
    """风险事件表（M5：风控拦截 / 阈值突破 记录，用于审计与前端告警）。

    event_type：
        ORDER_BLOCKED        下单被前置风控拦截
        CONCENTRATION_BREACH 单票/总仓位超上限
        DAILY_LOSS_BREACH    单日亏损触限
        STOP_LOSS_BREACH     个股浮亏触及止损线
    level：info / warn / high / critical
    """

    __tablename__ = "paper_risk_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    code = Column(String(20), default="", index=True)           # 相关标的（组合级为空）
    event_type = Column(String(30), index=True, nullable=False)
    level = Column(String(10), default="warn")                 # info/warn/high/critical
    message = Column(Text, default="")
    detail = Column(JSON)                                      # 结构化信息（阈值/实际值等）
    acked = Column(Boolean, default=False)                      # 是否已处理
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PaperRiskRule(Base):
    """智能风控中心 — 可配置规则引擎表（企业级增强，M5 风控的升级）。

    规则类型 rule_type：
        SECTOR_CONCENTRATION  行业集中度上限（detail.industry 可选；超阈值即告警）
        MAX_DRAWDOWN          账户最大回撤阈值（单位 %，如 25 表示 25%）
        LEVERAGE              持仓杠杆/仓位上限（单位 %，如 90 表示总仓位 90%）
        BLACKLIST             黑名单（detail.codes = ["600519", ...]，持仓命中即告警）
        OVERNIGHT_LIMIT       隔夜持仓占比上限（单位 %）
        CUSTOM                自定义（detail.condition = "always" 时强制触发，默认不触发）
    severity：warn / high / critical（决定告警级别与前端配色）
    account_id 为 NULL 表示全局规则（对所有账户生效）。
    """

    __tablename__ = "paper_risk_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=True)    # 关联 paper_accounts.id；NULL=全局
    name = Column(String(100), nullable=False)                # 规则名称（如「白酒板块限仓」）
    rule_type = Column(String(30), index=True, nullable=False)  # 见上 rule_type 说明
    threshold = Column(Float, default=0.0)                     # 数值阈值（按规则语义，多为百分比）
    scope = Column(String(20), default="account")             # account / global
    enabled = Column(Boolean, default=True)                    # 是否启用
    severity = Column(String(10), default="warn")              # warn / high / critical
    detail = Column(JSON)                                      # 结构化参数（如黑名单代码列表）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperEquitySnapshot(Base):
    """日级权益快照表（M6：资金与收益曲线 / 统计中心）。

    每个交易日对账户做一次「收盘权益」快照，构成收益曲线；由快照序列驱动
    M1 预留的 max_drawdown / sharpe_ratio 等历史型绩效字段。

    字段约定（与平台一致）：金额为「元」；日期为本地交易日 YYYY-MM-DD；
    盈亏率单位为「%」。daily_pnl 相对「前一交易日快照」计算，无前序时相对初始资金。
    """

    __tablename__ = "paper_equity_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "date", name="uq_paper_snap_account_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    date = Column(String(20), nullable=False)                  # YYYY-MM-DD
    total_assets = Column(Float, default=0.0)                  # 总资产（元）= 现金 + 持仓市值
    cash = Column(Float, default=0.0)                          # 现金（元）
    position_value = Column(Float, default=0.0)                # 持仓市值（元）
    daily_pnl = Column(Float, default=0.0)                     # 当日盈亏（元，相对前序快照）
    daily_pnl_pct = Column(Float, default=0.0)                 # 当日盈亏率(%)
    cumulative_pnl = Column(Float, default=0.0)                # 累计盈亏（元，相对初始资金）
    cumulative_pnl_pct = Column(Float, default=0.0)            # 累计收益率(%)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ============================================================
# 研究员 Agent（#182：自动挖掘因子、生成策略）
# ============================================================
class PaperResearchSession(Base):
    """研究员 Agent 一次研究会话。

    一次会话 = 对给定股票宇宙做因子挖掘 + 生成若干策略想法；
    mode 记录本次是「LLM 驱动」还是「规则确定性」生成，便于前端区分来源。
    """

    __tablename__ = "paper_research_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=True)     # 关联账户（全局研究为 NULL）
    universe = Column(JSON)                                     # 研究标的列表（代码）
    mode = Column(String(20), default="rule")                   # rule（规则）/ llm（大模型）
    model = Column(String(50), default="rule-based")            # 实际使用的模型标识
    summary = Column(Text, default="")                          # 研究结论摘要
    status = Column(String(20), default="completed")             # pending / running / completed / failed
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PaperFactorFinding(Base):
    """研究员 Agent 在某次会话中挖掘出的因子结论。"""

    __tablename__ = "paper_factor_findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, index=True, nullable=False)    # 关联会话
    name = Column(String(50), default="")                       # 因子名（如「20日动量」）
    factor_type = Column(String(30), default="")                 # momentum/volatility/reversal/rsi/volume/quality
    description = Column(Text, default="")                       # 因子说明
    direction = Column(String(20), default="neutral")            # long（偏多）/ short（偏空）/ neutral
    score = Column(Float, default=0.0)                          # 因子强度评分(0-100)
    detail = Column(JSON)                                        # 逐标的取值等明细
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PaperStrategyIdea(Base):
    """研究员 Agent 生成的策略想法（兼容事件驱动回测引擎的规则格式）。"""

    __tablename__ = "paper_strategy_ideas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, index=True, nullable=False)     # 关联会话
    account_id = Column(Integer, index=True, nullable=True)      # 关联账户（全局为 NULL）
    name = Column(String(100), default="")                       # 策略名
    description = Column(Text, default="")                       # 策略说明
    universe = Column(JSON)                                      # 适用标的列表
    entry_rules = Column(JSON)                                   # 入场规则（EventRule 列表）
    exit_rules = Column(JSON)                                    # 出场规则（EventRule 列表）
    risk = Column(JSON)                                          # 全局风控 {stopLoss, takeProfit}
    logic = Column(Text, default="")                             # 策略逻辑（人类可读）
    expected = Column(Text, default="")                          # 预期表现/适用场景
    backtest_run_id = Column(Integer, nullable=True, index=True)  # 关联回测 run（未回测为 NULL）
    backtested = Column(Boolean, default=False)                  # 是否已触发回测
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PaperPublishedStrategy(Base):
    """策略市场——已发布的策略。

    来源可以是：BacktestRun（回测 → 发布）、PaperStrategyIdea（研究员想法 → 发布）、手动创建。
    """

    __tablename__ = "paper_published_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    author_account_id = Column(Integer, index=True, nullable=False)
    name = Column(String(100), default="")
    description = Column(Text, default="")
    source_type = Column(String(20), default="manual")                # manual / backtest / idea
    source_id = Column(Integer, nullable=True)
    entry_rules = Column(JSON)
    exit_rules = Column(JSON)
    risk = Column(JSON)
    universe = Column(JSON)
    logic = Column(Text, default="")
    performance_snapshot = Column(JSON)
    tags = Column(JSON)
    version = Column(Integer, default=1)
    is_published = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperStrategySubscription(Base):
    """策略市场——用户订阅。"""

    __tablename__ = "paper_strategy_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    published_strategy_id = Column(Integer, index=True, nullable=False)
    local_strategy_id = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    unsubscribed_at = Column(DateTime, nullable=True)


class PaperStrategyRating(Base):
    """策略市场——用户评分与评价。"""

    __tablename__ = "paper_strategy_ratings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    published_strategy_id = Column(Integer, index=True, nullable=False)
    score = Column(Integer, default=5)
    review = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class PaperPortfolio(Base):
    """策略组合——将多个策略归组为统一组合，分配资金比例。"""

    __tablename__ = "paper_portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    name = Column(String(100), default="")
    description = Column(Text, default="")
    allocation = Column(JSON)                         # {strategy_id: weight_pct}
    total_capital = Column(Float, default=0.0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperPortfolioRebalance(Base):
    """组合再平衡记录。"""

    __tablename__ = "paper_portfolio_rebalances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, index=True, nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    reason = Column(String(200), default="")
    allocations_before = Column(JSON)
    allocations_after = Column(JSON)
    status = Column(String(20), default="done")
    notes = Column(Text, default="")


class PaperDailyReview(Base):
    """AI 每日复盘报告——模拟盘账户每日交易/持仓/市场回顾。"""

    __tablename__ = "paper_daily_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    date = Column(String(10), nullable=False, index=True)            # YYYY-MM-DD
    summary = Column(Text, default="")                               # 复盘总结文本
    trades_summary = Column(JSON)                                    # 今日成交汇总
    market_summary = Column(Text, default="")                        # 市场概况
    pnl_summary = Column(JSON)                                       # 盈亏归因
    performance = Column(JSON)                                       # 绩效快照
    decisions = Column(JSON)                                         # 交易决策回顾
    generated_by = Column(String(20), default="rule")                # rule / llm
    created_at = Column(DateTime, default=datetime.utcnow)


class PaperKlineCache(Base):
    """K 线数据本地持久化缓存（#P1：避免重复拉取 westock-data）。"""

    __tablename__ = "paper_kline_cache"
    __table_args__ = (
        UniqueConstraint("code", "date", name="uq_paper_kline_code_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    open = Column(Float, default=0.0)
    high = Column(Float, default=0.0)
    low = Column(Float, default=0.0)
    close = Column(Float, default=0.0)
    volume = Column(Float, default=0.0)
    period = Column(String(10), default="day")
    created_at = Column(DateTime, default=datetime.utcnow)