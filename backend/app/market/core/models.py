"""市场模块 ORM 模型。

覆盖需求 6（数据存储）：实时行情、历史K线、交易信号、策略结果，外加资金流与市场宽度快照。
所有表带 ``created_at`` 时间戳，并对高频查询字段（code / ts / period）建索引，支撑百万级标的。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now() -> datetime:
    return datetime.utcnow()


class RealtimeQuote(Base):
    """实时行情快照（按 code + ts 多版本留存，可回放）。"""

    __tablename__ = "market_realtime_quote"
    __table_args__ = (
        Index("ix_rt_quote_code_ts", "code", "ts"),
        Index("ix_rt_quote_ts", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(32), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    change: Mapped[float] = mapped_column(Float, default=0.0)          # 涨跌额
    change_pct: Mapped[float] = mapped_column(Float, default=0.0)      # 涨跌幅 %
    volume: Mapped[int] = mapped_column(BigInteger, default=0)         # 成交量（手）
    amount: Mapped[float] = mapped_column(Float, default=0.0)          # 成交金额（元）
    turnover: Mapped[float] = mapped_column(Float, default=0.0)         # 换手率 %
    pe: Mapped[float] = mapped_column(Float, default=0.0)
    pb: Mapped[float] = mapped_column(Float, default=0.0)
    total_mv: Mapped[float] = mapped_column(Float, default=0.0)        # 总市值（元）
    float_mv: Mapped[float] = mapped_column(Float, default=0.0)        # 流通市值（元）
    source: Mapped[str] = mapped_column(String(16), default="")        # 数据来源（tencent/...)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class KlineBar(Base):
    """多周期 K 线（分时/1m/5m/15m/30m/日/周/月）。"""

    __tablename__ = "market_kline"
    __table_args__ = (
        UniqueConstraint("code", "period", "dt", name="uq_kline_code_period_dt"),
        Index("ix_kline_code_period", "code", "period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[str] = mapped_column(String(8), nullable=False)     # minute/5min/.../day/week/month
    dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)    # K线时间
    open: Mapped[float] = mapped_column(Float, default=0.0)
    high: Mapped[float] = mapped_column(Float, default=0.0)
    low: Mapped[float] = mapped_column(Float, default=0.0)
    close: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CapitalFlow(Base):
    """实时资金流（主力/超大单/大单/中单/小单/北向）。"""

    __tablename__ = "market_capital_flow"
    __table_args__ = (Index("ix_cf_code_ts", "code", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(32), default="")
    main_in: Mapped[float] = mapped_column(Float, default=0.0)         # 主力净流入（元）
    ultra_large: Mapped[float] = mapped_column(Float, default=0.0)     # 超大单净流入
    large: Mapped[float] = mapped_column(Float, default=0.0)           # 大单净流入
    medium: Mapped[float] = mapped_column(Float, default=0.0)          # 中单净流入
    small: Mapped[float] = mapped_column(Float, default=0.0)           # 小单净流入
    northbound: Mapped[float] = mapped_column(Float, default=0.0)      # 北向资金（元，个股维度可能为空）
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MarketBreadth(Base):
    """市场宽度快照（涨跌家数 / 涨跌停）。"""

    __tablename__ = "market_breadth"
    __table_args__ = (Index("ix_breadth_date", "trade_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    total: Mapped[int] = mapped_column(Integer, default=0)
    up: Mapped[int] = mapped_column(Integer, default=0)
    down: Mapped[int] = mapped_column(Integer, default=0)
    flat: Mapped[int] = mapped_column(Integer, default=0)
    limit_up: Mapped[int] = mapped_column(Integer, default=0)
    limit_down: Mapped[int] = mapped_column(Integer, default=0)
    northbound: Mapped[float] = mapped_column(Float, default=0.0)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class TradeSignal(Base):
    """交易信号（由策略/规则产生，供 AI 量化接口消费）。"""

    __tablename__ = "market_trade_signal"
    __table_args__ = (Index("ix_signal_code_ts", "code", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(32), default="")
    signal_type: Mapped[str] = mapped_column(String(16), default="")   # buy/sell/hold/watch
    strength: Mapped[float] = mapped_column(Float, default=0.0)        # 信号强度 [-1,1]
    price: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="rule")   # rule/ai/model
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class StrategyResult(Base):
    """策略回测/运行结果（需求 6：策略结果落地）。"""

    __tablename__ = "market_strategy_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(128), default="")
    code: Mapped[str] = mapped_column(String(16), default="")          # 适用标的（空=组合/市场级）
    start_date: Mapped[str] = mapped_column(String(10), default="")
    end_date: Mapped[str] = mapped_column(String(10), default="")
    total_return: Mapped[float] = mapped_column(Float, default=0.0)
    annual_return: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    params: Mapped[Text] = mapped_column(Text, default="{}")           # JSON
    metrics: Mapped[Text] = mapped_column(Text, default="{}")          # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AIScore(Base):
    """AI 选股评分（需求 5：AI评分；需求 9：AI选股评分展示）。"""

    __tablename__ = "market_ai_score"
    __table_args__ = (Index("ix_ai_code_ts", "code", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(32), default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)           # 综合评分 [0,100]
    tech_score: Mapped[float] = mapped_column(Float, default=0.0)
    fund_score: Mapped[float] = mapped_column(Float, default=0.0)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    momentum: Mapped[float] = mapped_column(Float, default=0.0)        # 动量因子
    volatility: Mapped[float] = mapped_column(Float, default=0.0)      # 波动率
    risk_level: Mapped[str] = mapped_column(String(8), default="")    # low/mid/high
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
