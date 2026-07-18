"""模拟盘交易系统 — 行情数据服务（M2）。

职责：对外提供「实时行情 / 五档盘口 / K线（含分钟级）/ 资金流向 / 行业·概念板块 /
主要指数」的统一数据接口。

数据源策略（与平台 data_provider 一致 —— 真实优先，失败回退模拟）：
- 真实源：优先使用 AKShare（用户技术栈指定）对接东方财富等公开行情接口；
  主要指数与日/周/月 K线也可复用既有 data_provider（westock 真实源）。
- 回退源：当本环境无外网（沙箱常见）或接口异常时，自动切换为内置模拟器，
  生成贴近真实分布的行情数据，保证系统在任何环境都可运行与演示。
- 每个接口返回 dict 均带 `dataSource` 字段（"akshare" / "mock"），便于前端与
  测试识别当前处于真实还是模拟模式。

说明：
- A 股无免费交易所直连 tick 源，分钟级 K线通过 AKShare 的「东方财富分钟行情」
  获取；模拟模式下用本地随机游走生成，仅供策略/撮合联调，不构成真实行情。
- 所有对外价格单位为「元/股」，成交量为「手」，成交额为「元」，与交易系统一致。
"""
import hashlib
import logging
import math
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

# 复用平台既有数据层（代码转换、指标、指数、K线），避免重复造轮子
from app.services.data_provider import (
    to_westock_code,
    get_indices as _dp_get_indices,
    get_stock_kline as _dp_get_kline,
)
# 真实行情源：腾讯自选股（qt.gtimg.cn）。批量拉取 + 共享缓存，进程内所有
# quote / WS 推送共用，彻底规避 AKShare 在 uvloop 下不可用的问题。
from app.paper.services import tencent_quote

logger = logging.getLogger(__name__)

# 内存缓存（TTL 秒），避免重复打外部接口
_CACHE: dict[str, tuple[float, object]] = {}
CACHE_TTL = int(__import__("os").environ.get("PAPER_MARKET_TTL", "15"))  # 秒
# 各接口独立 TTL：行情刷新快，K线可久
_TTL = {
    "quote": int(__import__("os").environ.get("PAPER_TTL_QUOTE", "10")),
    "orderbook": int(__import__("os").environ.get("PAPER_TTL_ORDERBOOK", "10")),
    "kline": int(__import__("os").environ.get("PAPER_TTL_KLINE", "120")),
    "capital": int(__import__("os").environ.get("PAPER_TTL_CAPITAL", "60")),
    "sector": int(__import__("os").environ.get("PAPER_TTL_SECTOR", "120")),
}


def _cached(key: str, fetcher, ttl: int = CACHE_TTL):
    now = time.time()
    if key in _CACHE:
        ts, val = _CACHE[key]
        if now - ts < ttl:
            return val
    val = fetcher()
    _CACHE[key] = (now, val)
    return val


def _to_float(v, default=0.0):
    try:
        if v in (None, "", "-"):
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _seed_of(code: str) -> int:
    """由股票代码派生稳定随机种子，保证同一标的模拟数据可复现。"""
    return int(hashlib.md5(code.encode("utf-8")).hexdigest(), 16) % (2**31)


# —— 标的静态属性（用于模拟器生成贴近真实的名称/基准价）——
_NAME_POOL = [
    "贵州茅台", "宁德时代", "中国平安", "五粮液", "招商银行", "隆基绿能", "比亚迪",
    "东方财富", "中信证券", "京东方A", "格力电器", "美的集团", "三一重工", "恒瑞医药",
    "伊利股份", "海康威视", "立讯精密", "阳光电源", "北方华创", "兆易创新",
]
_INDEX_NAME = {"000001.SH": "上证指数", "399001.SZ": "深证成指", "399006.SZ": "创业板指",
               "000300.SH": "沪深300", "000905.SH": "中证500"}


def _name_of(code: str) -> str:
    if code in _INDEX_NAME:
        return _INDEX_NAME[code]
    rnd = random.Random(_seed_of(code))
    return rnd.choice(_NAME_POOL)


def _base_price(code: str) -> float:
    """由代码派生一个稳定的基准价（10~300 之间）。"""
    rnd = random.Random(_seed_of(code) + 7)
    return round(10 + rnd.random() * 290, 2)


# ============================================================
# 模拟器（沙箱兜底）
# ============================================================
def _sim_quote(code: str) -> dict:
    rnd = random.Random(_seed_of(code) + int(time.time() // 30))
    base = _base_price(code)
    prev_close = round(base * (1 + (rnd.random() - 0.5) * 0.02), 2)
    open_px = round(prev_close * (1 + (rnd.random() - 0.5) * 0.01), 2)
    price = round(open_px * (1 + (rnd.random() - 0.5) * 0.04), 2)
    high = round(max(open_px, price) * (1 + rnd.random() * 0.02), 2)
    low = round(min(open_px, price) * (1 - rnd.random() * 0.02), 2)
    change = round(price - prev_close, 2)
    change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0
    amplitude = round((high - low) / prev_close * 100, 2) if prev_close else 0.0
    volume = round(_base_volume(code) * (0.5 + rnd.random()), 0)
    amount = round(volume * price * 100, 0)  # 手→股×价
    turnover = round(rnd.random() * 5, 2)
    return {
        "code": code, "name": _name_of(code), "price": price, "prevClose": prev_close,
        "open": open_px, "high": high, "low": low, "volume": volume, "amount": amount,
        "turnover": turnover, "amplitude": amplitude, "change": change,
        "changePct": change_pct, "time": datetime.now().isoformat(timespec="seconds"),
        "dataSource": "mock",
    }


def _base_volume(code: str) -> float:
    rnd = random.Random(_seed_of(code) + 13)
    return round(50000 + rnd.random() * 450000, 0)


def _sim_order_book(code: str) -> dict:
    q = _sim_quote(code)
    price = q["price"]
    rnd = random.Random(_seed_of(code) + 3)
    spread = max(0.01, round(price * 0.0005, 2))
    bids, asks = [], []
    for i in range(5):
        bp = round(price - spread * (i + 1), 2)
        ap = round(price + spread * (i + 1), 2)
        bids.append({"price": bp, "volume": round(_base_volume(code) * (0.2 + rnd.random() * 0.5), 0)})
        asks.append({"price": ap, "volume": round(_base_volume(code) * (0.2 + rnd.random() * 0.5), 0)})
    return {
        "code": code, "name": q["name"], "bids": bids, "asks": asks,
        "time": q["time"], "dataSource": "mock",
    }


def _sim_kline(code: str, period: str, limit: int) -> list[dict]:
    rnd = random.Random(_seed_of(code) + hash(period) % 1000)
    base = _base_price(code)
    points = []
    if period in ("day", "week", "month"):
        start = datetime(2024, 1, 1)
        step = {"day": timedelta(days=1), "week": timedelta(days=7), "month": timedelta(days=30)}[period]
        cur = start
        px = base
        while len(points) < limit:
            if period != "week" or cur.weekday() == 0:
                if period != "month" or cur.day == 1:
                    if cur.weekday() < 5:
                        op = px
                        px = round(px * (1 + (rnd.random() - 0.48) * 0.04), 2)
                        hi = round(max(op, px) * (1 + rnd.random() * 0.02), 2)
                        lo = round(min(op, px) * (1 - rnd.random() * 0.02), 2)
                        points.append({"date": cur.strftime("%Y-%m-%d"), "open": op, "close": px,
                                       "high": hi, "low": lo, "volume": round(_base_volume(code) * (0.5 + rnd.random()), 0)})
            cur += step
    else:  # 分钟级：取最近交易日集合竞价至收盘
        minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}[period]
        days = max(1, math.ceil(limit * minutes / 240))
        cur = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        cur -= timedelta(days=days + 5)
        px = base
        count = 0
        while count < limit:
            if cur.weekday() < 5:
                if (cur.hour == 9 and cur.minute >= 30) or (10 <= cur.hour <= 11) or (13 <= cur.hour <= 14) or (cur.hour == 15 and cur.minute == 0):
                    op = px
                    px = round(px * (1 + (rnd.random() - 0.5) * 0.006), 2)
                    hi = round(max(op, px) * (1 + rnd.random() * 0.004), 2)
                    lo = round(min(op, px) * (1 - rnd.random() * 0.004), 2)
                    points.append({"date": cur.strftime("%Y-%m-%d %H:%M"), "open": op, "close": px,
                                   "high": hi, "low": lo, "volume": round(_base_volume(code) * 0.05 * (0.5 + rnd.random()), 0)})
                    count += 1
            cur += timedelta(minutes=minutes)
    return points[-limit:]


def _sim_capital_flow(code: str) -> dict:
    rnd = random.Random(_seed_of(code) + 21)
    total = round((_base_volume(code) * _base_price(code) * 100) * 0.02, 0)
    super_large = round(total * (rnd.random() - 0.4), 0)
    large = round(total * (rnd.random() - 0.4), 0)
    medium = round(total * (rnd.random() - 0.5), 0)
    small = round(total * (rnd.random() - 0.5), 0)
    main = super_large + large
    return {
        "code": code, "name": _name_of(code),
        "mainInflow": main, "netInflow": main,
        "superLarge": super_large, "large": large, "medium": medium, "small": small,
        "time": datetime.now().isoformat(timespec="seconds"), "dataSource": "mock",
    }


def _sim_sectors(kind: str) -> list[dict]:
    rnd = random.Random(_seed_of(kind))
    if kind == "industry":
        names = ["银行", "白酒", "半导体", "新能源车", "光伏", "医药", "券商", "房地产", "钢铁", "煤炭", "电力", "化工"]
    else:
        names = ["人工智能", "机器人", "低空经济", "华为概念", "ChatGPT", "锂电池", "氢能源", "数字货币", "元宇宙", "边缘计算"]
    out = []
    for i, n in enumerate(names):
        seed = _seed_of(kind + n)
        rr = random.Random(seed)
        change_pct = round((rr.random() - 0.45) * 4, 2)
        out.append({
            "code": f"{kind[:1].upper()}{i:02d}", "name": n, "changePct": change_pct,
            "leader": _name_of(f"{kind}{i}"), "leaderCode": f"{100000 + seed % 900000}",
            "dataSource": "mock",
        })
    return sorted(out, key=lambda x: -x["changePct"])


# ============================================================
# 真实源封装（AKShare）
# ============================================================
def _try_akshare():
    """惰性导入 AKShare；不可用时返回 None。"""
    try:
        import akshare as ak  # noqa: F401
        return ak
    except Exception:
        return None


# —— 网络可达性探测（带缓存，避免每次 status 都打外网）——
_net_cache: dict[str, object] = {"ts": 0.0, "ok": False}
_NET_TTL = 60.0


def _network_reachable() -> bool:
    """探测真实行情源（腾讯）是否可达（带 60s 缓存）。

    直接复用腾讯批量拉取的最近健康状态：上一次成功即视为可达，
    无需再打一次接口（避免无谓请求）。
    """
    now = time.time()
    if now - _net_cache["ts"] < _NET_TTL:  # type: ignore[operator]
        return bool(_net_cache["ok"])  # type: ignore[typeddict-item]
    ok = bool(tencent_quote.health()["ok"])
    _net_cache.update(ts=now, ok=ok)
    return ok


def _real_quote(code: str) -> Optional[dict]:
    """从腾讯实时行情（共享缓存）读取单只行情。

    腾讯接口在该环境实测可用，返回价格 / 涨跌幅 / 成交量 / 成交额 / 振幅 /
    五档盘口 / 时间戳等关键字段，``dataSource`` 标记为 ``tencent``。
    拉取失败（网络/解析）时返回 None，由上层 ``MarketProvider.quote`` 回退模拟。
    """
    q = tencent_quote.get_quote(code)
    if q is None:
        return None
    # 直接复用腾讯解析结果（已含前端所需全部字段 + dataSource="tencent"）
    return q


def _real_order_book(code: str) -> Optional[dict]:
    """五档盘口：优先从已拉取的腾讯行情提取（同一批量请求，零额外开销）。

    注：原 AKShare 盘口接口在本环境代理 502 + uvloop 不可用，已弃用；
    腾讯行情本身携带五档买卖盘，足以支撑盘口展示，无需独立网络调用。
    """
    try:
        ob = tencent_quote.get_order_book(code)
        if ob is None:
            return None
        return ob
    except Exception as e:  # noqa: BLE001
        logger.warning("[market_provider] 盘口获取异常 code=%s: %s", code, e)
        return None


_PERIOD_AK = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60",
              "day": "daily", "week": "weekly", "month": "monthly"}


def _real_kline(code: str, period: str, limit: int) -> Optional[list[dict]]:
    ak = _try_akshare()
    if ak is None or period not in _PERIOD_AK:
        return None
    try:
        if period in ("day", "week", "month"):
            df = ak.stock_zh_a_hist(symbol=code, period=_PERIOD_AK[period],
                                    start_date="20230101", adjust="qfq")
            date_col, o, c, h, l, v = "日期", "开盘", "收盘", "最高", "最低", "成交量"
        else:
            df = ak.stock_zh_a_hist_min_em(symbol=code, period=_PERIOD_AK[period], adjust="qfq")
            date_col, o, c, h, l, v = "时间", "开盘", "收盘", "最高", "最低", "成交量"
        if df is None or df.empty:
            return None
        pts = []
        for _, r in df.iterrows():
            pts.append({"date": str(r[date_col]), "open": _to_float(r[o]), "close": _to_float(r[c]),
                        "high": _to_float(r[h]), "low": _to_float(r[l]), "volume": _to_float(r[v])})
        return pts[-limit:]
    except Exception:
        return None


def _real_capital_flow(code: str) -> Optional[dict]:
    ak = _try_akshare()
    if ak is None:
        return None
    try:
        df = ak.stock_individual_fund_flow(stock=code, market="sh")
        if df is None or df.empty:
            return None
        r = df.iloc[-1]
        return {
            "code": code, "name": _name_of(code),
            "mainInflow": _to_float(r.get("主力净流入-净额")),
            "netInflow": _to_float(r.get("主力净流入-净额")),
            "superLarge": _to_float(r.get("超大单净流入-净额")),
            "large": _to_float(r.get("大单净流入-净额")),
            "medium": _to_float(r.get("中单净流入-净额")),
            "small": _to_float(r.get("小单净流入-净额")),
            "time": datetime.now().isoformat(timespec="seconds"), "dataSource": "akshare",
        }
    except Exception:
        return None


def _real_sectors(kind: str) -> Optional[list[dict]]:
    ak = _try_akshare()
    if ak is None:
        return None
    try:
        if kind == "industry":
            df = ak.stock_board_industry_name_em()
            nm, cp = "板块名称", "涨跌幅"
        else:
            df = ak.stock_board_concept_name_em()
            nm, cp = "板块名称", "涨跌幅"
        if df is None or df.empty:
            return None
        out = []
        for i, (_, r) in enumerate(df.iterrows()):
            out.append({"code": f"{kind[:1].upper()}{i:02d}", "name": str(r[nm]),
                        "changePct": _to_float(r[cp]), "leader": str(r.get("领涨股", "")),
                        "leaderCode": "", "dataSource": "akshare"})
        return out
    except Exception:
        return None


# ============================================================
# 统一对外接口
# ============================================================
class MarketProvider:
    """行情数据服务。对外暴露统一方法，内部真实优先、失败回退模拟。"""

    def quote(self, code: str) -> dict:
        def _f():
            real = _real_quote(code)
            return real or _sim_quote(code)
        return _cached(f"quote:{code}", _f, _TTL["quote"])

    def order_book(self, code: str) -> dict:
        def _f():
            real = _real_order_book(code)
            return real or _sim_order_book(code)
        return _cached(f"ob:{code}", _f, _TTL["orderbook"])

    def kline(self, code: str, period: str = "day", limit: int = 120) -> dict:
        period = period or "day"
        if period not in _PERIOD_AK:
            period = "day"
        limit = max(10, min(limit, 500))
        key = f"kline:{code}:{period}:{limit}"
        def _f():
            real = _real_kline(code, period, limit)
            pts = real if real else _sim_kline(code, period, limit)
            name = _name_of(code)
            try:
                name = self.quote(code)["name"]
            except Exception:
                pass
            return {"code": code, "name": name, "period": period,
                    "points": pts, "dataSource": "akshare" if real else "mock"}
        return _cached(key, _f, _TTL["kline"])

    def capital_flow(self, code: str) -> dict:
        def _f():
            real = _real_capital_flow(code)
            return real or _sim_capital_flow(code)
        return _cached(f"cap:{code}", _f, _TTL["capital"])

    def sectors(self, kind: str = "industry") -> list[dict]:
        kind = "industry" if kind not in ("industry", "concept") else kind
        def _f():
            real = _real_sectors(kind)
            return real if real else _sim_sectors(kind)
        return _cached(f"sector:{kind}", _f, _TTL["sector"])

    def indices(self) -> list[dict]:
        """主要指数 —— 复用平台既有 data_provider（westock 真实源 + 回退）。"""
        try:
            return _dp_get_indices()
        except Exception:
            return []

    def status(self) -> dict:
        net = _network_reachable()
        tq = tencent_quote.health()
        return {
            # 真实源为腾讯自选股（qt.gtimg.cn）
            "realSource": "tencent",
            # 实时探测主行情接口是否可达
            "networkReachable": net,
            # 网络可达 → 真实模式；否则全局回退模拟
            "mode": "real" if net else "mock",
            "cacheEntries": len(_CACHE),
            # 腾讯行情最近一次拉取健康状态（决定 dataSource 取值）
            "tencent": tq,
            # 关键：每个接口返回自带 dataSource 字段，前端应以此为准判断单次数据真实性
            "note": "每个接口的 dataSource 字段返回该次调用实际使用的源（tencent/mock）。",
        }


# 单例（供路由 / WS 共用）
market_provider = MarketProvider()
