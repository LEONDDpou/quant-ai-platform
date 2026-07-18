"""ORM 模型 — AI量化平台持久化。

覆盖对象：
- AIReport            每日 AI 研究员报告（LLM 生成或规则合成，均落库）
- BacktestResult      回测结果（基于真实 K线）
- NewsItem            市场新闻（去重缓存）
- MarketSnapshot      WebSocket 实时行情快照（时间序列）
- Strategy            策略中心（用户创建/启停的策略元数据）
- MarketTemperature   市场温度记录（时间序列）            [v1.0 新增]
- FactorScore         多因子评分（单股）                  [v1.0 新增]
- Alert               预警记录                            [v1.0 新增]
- AlertRule           预警规则配置                        [v1.0 新增]
- AIMarketJudgment    AI 市场研判记录                      [v1.0 新增]
- AgentTask           AI Agent 任务记录                   [v1.0 新增]
- PortfolioPosition   组合持仓                            [v1.1 新增]
- PortfolioOrder      组合订单                            [v1.1 新增]
- PortfolioSnapshot   组合日快照                          [v1.1 新增]
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.db.database import Base


class AIReport(Base):
    __tablename__ = "ai_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(20), index=True)            # YYYY-MM-DD
    market_summary = Column(Text)
    up_reasons = Column(JSON)                        # list[str]
    risk_factors = Column(JSON)                      # list[str]
    focus_stocks = Column(JSON)                      # list[dict]
    sentiment_score = Column(Integer)
    ai_judgment = Column(String(20))                 # bullish/neutral/bearish
    outlook = Column(Text)
    llm_enabled = Column(Boolean, default=False)
    model = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(100))
    symbol = Column(String(20), index=True)
    start_date = Column(String(20))
    end_date = Column(String(20))
    initial_capital = Column(Float)
    total_return = Column(Float)
    annualized_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    avg_hold_days = Column(Float)
    equity_curve = Column(JSON)                      # list[{date,value}]
    trades = Column(JSON)                            # list[dict]
    data_source = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)


class NewsItem(Base):
    __tablename__ = "news_items"
    __table_args__ = (UniqueConstraint("unique_key", name="uq_news_unique_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_key = Column(String(600), unique=True, index=True)  # title|time
    title = Column(String(500))
    source = Column(String(100))
    time = Column(String(50))
    sentiment = Column(String(20))                   # positive/negative/neutral
    impact = Column(Integer)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    payload = Column(JSON)                           # {indices:[...], stocks:[...]}


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(String(50), primary_key=True)
    name = Column(String(100))
    type = Column(String(50))
    pool = Column(String(50))
    status = Column(String(20))                      # running/stopped/backtesting
    description = Column(Text)
    params = Column(JSON)                            # 策略参数
    metrics = Column(JSON)                           # 最新绩效指标
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================
# v1.0 新增模型
# ============================================================
class MarketTemperature(Base):
    """市场温度记录（时间序列）"""
    __tablename__ = "market_temperature"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    score = Column(Float)                            # 0-100 综合温度
    valuation = Column(Float)                        # 估值温度
    sentiment = Column(Float)                        # 情绪温度
    capital = Column(Float)                          # 资金温度
    technical = Column(Float)                        # 技术温度
    risk_level = Column(String(20))                  # extreme_low/low/medium/high/extreme_high
    created_at = Column(DateTime, default=datetime.utcnow)


class FactorScore(Base):
    """多因子评分（单股）"""
    __tablename__ = "factor_scores"
    __table_args__ = (UniqueConstraint("date", "code", name="uq_factor_score_date_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    code = Column(String(20), nullable=False, index=True)
    total_score = Column(Float)                      # 综合评分(0-100)
    percentile = Column(Float)                       # 全市场百分位
    value_score = Column(Float)                      # 估值因子分
    quality_score = Column(Float)                    # 质量因子分
    momentum_score = Column(Float)                   # 动量因子分
    volatility_score = Column(Float)                 # 波动因子分
    sentiment_score = Column(Float)                  # 情绪因子分
    detail = Column(JSON)                            # 因子原始值+标准化值
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """预警记录"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(30), nullable=False, index=True)  # technical/capital/event/risk
    severity = Column(String(10), nullable=False)          # info/warning/critical
    code = Column(String(20))
    title = Column(String(200))
    message = Column(Text)
    trigger_condition = Column(Text)
    is_read = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AlertRule(Base):
    """预警规则配置"""
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    type = Column(String(30))                        # technical/capital/event/risk
    condition = Column(JSON)                         # 触发条件配置
    enabled = Column(Boolean, default=True)
    cooldown_min = Column(Integer, default=5)        # 冷却时间（分钟）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIMarketJudgment(Base):
    """AI 市场研判记录"""
    __tablename__ = "ai_market_judgments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    market_trend = Column(String(30))                # 大盘判断
    risk_stars = Column(Integer)                     # 风险星级(1-5)
    opportunities = Column(JSON)                     # 机会板块列表
    advice = Column(Text)                            # 操作建议
    ai_score = Column(Integer)                       # AI综合评分(0-100)
    dimensions = Column(JSON)                        # 五维度评分详情
    buy_probability = Column(String(50))             # 买入概率描述
    generated_by = Column(String(50))                # 生成Agent名称
    model = Column(String(50))                       # LLM模型
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentTask(Base):
    """AI Agent 任务记录"""
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(50))                  # MarketMacro/SectorRotation/StrategyAdvisor/...
    task_type = Column(String(50))                   # market_judgment/sector_analysis/strategy_generation
    input_data = Column(JSON)
    output_data = Column(JSON)
    status = Column(String(20), default="pending")   # pending/running/completed/failed
    error_msg = Column(Text)
    model = Column(String(50))
    tokens_used = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


# ============================================================
# v1.1 新增模型 — 组合管理
# ============================================================
class PortfolioPosition(Base):
    """组合持仓"""
    __tablename__ = "portfolio_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(50))
    shares = Column(Integer, default=0)
    avg_cost = Column(Float, default=0.0)            # 平均成本
    current_price = Column(Float, default=0.0)        # 最新价（快照）
    industry = Column(String(50))                     # 行业分类
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PortfolioOrder(Base):
    """组合订单"""
    __tablename__ = "portfolio_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(50))
    direction = Column(String(10), nullable=False)     # buy/sell
    price = Column(Float, default=0.0)
    shares = Column(Integer, default=0)
    amount = Column(Float, default=0.0)                # 成交金额
    status = Column(String(20), default="pending")     # pending/filled/cancelled
    reason = Column(Text)                              # 交易理由
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PortfolioSnapshot(Base):
    """组合日快照"""
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (UniqueConstraint("date", name="uq_portfolio_snap_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    total_value = Column(Float, default=0.0)
    cash = Column(Float, default=0.0)
    position_value = Column(Float, default=0.0)
    daily_pnl = Column(Float, default=0.0)
    daily_pnl_pct = Column(Float, default=0.0)
    cumulative_pnl = Column(Float, default=0.0)
    cumulative_pnl_pct = Column(Float, default=0.0)
    positions = Column(JSON)                           # 当日持仓快照
    metrics = Column(JSON)                             # 风险指标快照
    created_at = Column(DateTime, default=datetime.utcnow)
