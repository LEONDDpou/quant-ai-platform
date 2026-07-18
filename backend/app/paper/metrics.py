"""Prometheus 指标定义（#P1）。

可以被 order_service / risk_service / match_engine 等导入并调用。
"""
from prometheus_client import Counter, Histogram, Gauge

# 订单计数（标签：direction=buy/sell, status=pending/filled/cancelled）
ORDER_COUNTER = Counter(
    "paper_orders_total", "Total orders placed",
    ["direction", "status"],
)

# 撮合延迟（秒）
MATCH_LATENCY = Histogram(
    "paper_match_seconds", "Order match latency in seconds",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

# 风控拦截计数（标签：rule_type=price_limit/self_trade/concentration/etc）
RISK_BLOCKED = Counter(
    "paper_risk_blocked_total", "Orders blocked by risk rules",
    ["rule_type"],
)

# 活跃策略数（标签：account_id）
ACTIVE_STRATEGIES = Gauge(
    "paper_active_strategies", "Number of active auto-trade strategies",
    ["account_id"],
)

# 待撮合订单数
PENDING_ORDERS = Gauge(
    "paper_pending_orders", "Number of pending orders awaiting match",
)

# 账户持仓数
POSITION_COUNT = Gauge(
    "paper_position_count", "Total positions across all accounts",
)
