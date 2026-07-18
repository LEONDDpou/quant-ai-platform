"""模拟盘交易系统 — A股交易规则（撮合约束）。

集中实现中国A股市场的交易规则，供撮合引擎（order_service）调用：
- 交易时间（集合竞价 / 连续竞价 / 午休）
- 涨跌停限制（普通±10% / ST±5% / 创业板·科创板±20%）
- 最小交易单位（100 股/手，整手倍数）
- 费用模型（佣金 + 印花税 + 过户费）
- T+1 可卖数量推导

所有金额单位「元」、价格「元/股」、数量「股」，与 ORM 与行情系统一致。

说明（M3 已知简化，详见交付说明）：
- 科创板/创业板「200股递增」的特殊最小变动单位规则未实现，仍按 100 股/手处理；
- 集合竞价按连续竞价同价撮合近似处理，未单独建模 9:15-9:25 / 14:57-15:00 的撮合机制；
- 涨跌停以昨收为基准计算（盘中封板价固定），不模拟「开板」动态。
"""
from datetime import datetime, time

# —— 费用参数（可通过环境变量覆盖，单位：比率 / 元）——
import os

COMMISSION_RATE = float(os.environ.get("PAPER_COMMISSION_RATE", "0.00025"))  # 佣金 万2.5
COMMISSION_MIN = float(os.environ.get("PAPER_COMMISSION_MIN", "5.0"))        # 佣金最低 5 元
STAMP_RATE = float(os.environ.get("PAPER_STAMP_RATE", "0.0005"))             # 印花税 千0.5（仅卖出）
TRANSFER_RATE = float(os.environ.get("PAPER_TRANSFER_RATE", "0.00001"))      # 过户费 万0.1（双边）

LOT_SIZE = 100  # 最小交易单位（股）

# 涨跌停幅度
LIMIT_NORMAL = 0.10   # 普通股票 ±10%
LIMIT_ST = 0.05       # ST / *ST ±5%
LIMIT_STAR = 0.20     # 创业板(300/301) / 科创板(688/689) ±20%

# 交易时段（含集合竞价窗口，撮合在此区间内允许）
_TRADING_WINDOWS = (
    (time(9, 15), time(11, 30)),
    (time(13, 0), time(15, 0)),
)


def is_trading_time(dt: datetime | None = None) -> bool:
    """判断当前是否为可交易时段（含集合竞价）。

    A股交易日为周一至周五；时段：9:15-11:30 与 13:00-15:00，午休 11:30-13:00 不可交易。
    """
    dt = dt or datetime.now()
    if dt.weekday() >= 5:  # 周六周日
        return False
    t = dt.time()
    return any(start <= t <= end for start, end in _TRADING_WINDOWS)


def _limit_ratio(code: str, is_st: bool) -> float:
    """根据代码前缀与 ST 标识返回涨跌停幅度。"""
    if is_st:
        return LIMIT_ST
    if code.startswith(("300", "301")):   # 创业板
        return LIMIT_STAR
    if code.startswith(("688", "689")):    # 科创板
        return LIMIT_STAR
    return LIMIT_NORMAL


def price_limit(code: str, prev_close: float, is_st: bool = False) -> tuple[float, float]:
    """返回 (跌停价, 涨停价)，四舍五入到分。

    A股价格最小变动单位为 0.01 元，涨跌停价按昨收 ×(1±幅度) 四舍五入。
    """
    ratio = _limit_ratio(code, is_st)
    low = round(prev_close * (1 - ratio), 2)
    high = round(prev_close * (1 + ratio), 2)
    return low, high


def validate_price_in_limit(code: str, price: float, prev_close: float, is_st: bool = False) -> bool:
    """校验委托价是否在涨跌停区间内（含边界）。"""
    if prev_close <= 0:
        return True  # 无昨收（如新股）时不强约束
    low, high = price_limit(code, prev_close, is_st)
    return low - 1e-9 <= price <= high + 1e-9


def validate_lot(quantity: int) -> bool:
    """校验数量是否为整手（100 股的整数倍，且 > 0）。"""
    return quantity > 0 and quantity % LOT_SIZE == 0


def estimate_fee(direction: str, amount: float) -> float:
    """估算单边交易费用（元）。

    amount：成交金额 = 成交价 × 成交量。
    - 佣金：max(最低, 金额×佣金率)，双边收取；
    - 过户费：金额×过户费率，双边收取；
    - 印花税：金额×印花税率，仅「卖出」收取。
    """
    commission = max(COMMISSION_MIN, amount * COMMISSION_RATE)
    transfer = amount * TRANSFER_RATE
    stamp = amount * STAMP_RATE if direction == "sell" else 0.0
    return round(commission + transfer + stamp, 2)


def max_affordable_shares(cash: float, price: float) -> int:
    """在给定现金与价格下，扣除佣金/过户费后最大可买整手数（股）。"""
    if price <= 0:
        return 0
    # 近似：先按价格估算可买手数，再逐手校验费用
    est = int(cash // (price * LOT_SIZE))
    est = max(0, est)
    while est > 0:
        qty = est * LOT_SIZE
        fee = estimate_fee("buy", price * qty)
        if price * qty + fee <= cash + 1e-6:
            return qty
        est -= 1
    return 0


def is_star_market(code: str) -> bool:
    """是否创业板/科创板（±20% 涨跌停）。"""
    return code.startswith(("300", "301", "688", "689"))
