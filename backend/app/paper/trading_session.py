"""A 股交易时段判断（#P0）。

用于撮合引擎在非交易时段屏蔽撮合、集合竞价阶段不做逐笔成交。
"""
import datetime


# 涨跌停幅度（A 股）
PRICE_LIMITS = {
    "normal": 0.10,   # 主板 ±10%
    "st": 0.05,       # ST/*ST ±5%
    "cn": 0.20,       # 创业板 ±20%（300xxx）
    "kc": 0.20,       # 科创板 ±20%（688xxx）
    "bj": 0.30,       # 北交所 ±30%（8xxxxx）
}


def get_price_limit_pct(code: str) -> float:
    """根据代码判断涨跌停幅度。"""
    if code.startswith("300") or code.startswith("688"):
        return 0.20
    if code.startswith("8"):
        return 0.30
    return 0.10  # 主板默认


def is_st_stock(name: str = "") -> bool:
    """通过名称判断是否为 ST/*ST。"""
    if not name:
        return False
    return name.startswith("ST") or name.startswith("*ST") or "ST" in name


def get_st_price_limit_pct(name: str = "") -> float:
    """ST 股票涨跌停幅度 5%。"""
    if is_st_stock(name):
        return 0.05
    return 0.10


class TradingSession:
    """A 股交易时段状态机。"""

    PRE_OPEN = "pre_open"       # 集合竞价 9:15-9:25
    CONTINUOUS = "continuous"   # 连续竞价 9:30-11:30 / 13:00-14:57
    PRE_CLOSE = "pre_close"     # 收盘集合竞价 14:57-15:00
    CLOSED = "closed"           # 非交易时间

    @staticmethod
    def current() -> str:
        """返回当前交易时段。"""
        now = datetime.datetime.now()
        if now.weekday() >= 5:  # 周末
            return TradingSession.CLOSED
        hm = now.hour * 100 + now.minute
        if 915 <= hm <= 925:
            return TradingSession.PRE_OPEN
        if 930 <= hm <= 1130 or 1300 <= hm <= 1457:
            return TradingSession.CONTINUOUS
        if 1457 <= hm <= 1500:
            return TradingSession.PRE_CLOSE
        return TradingSession.CLOSED

    @staticmethod
    def can_trade() -> bool:
        """当前是否允许下单和撮合。"""
        session = TradingSession.current()
        return session in (TradingSession.CONTINUOUS, TradingSession.PRE_OPEN)

    @staticmethod
    def can_match() -> bool:
        """当前是否允许逐笔撮合。集合竞价阶段不逐笔成交。"""
        return TradingSession.current() == TradingSession.CONTINUOUS

    @staticmethod
    def can_cancel() -> bool:
        """当前是否允许撤单。收盘集合竞价期间不接受撤单。"""
        return TradingSession.current() != TradingSession.PRE_CLOSE
