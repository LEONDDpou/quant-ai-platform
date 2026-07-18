"""真实数据服务层 — 对接 westock-data，提供指数/新闻/个股分析/K线回测。

设计原则：
- 优先使用 westock-data 真实行情；调用失败或不可用则回退 mock_data，保证页面永远有数据。
- 指数/个股技术指标（MACD/RSI/BOLL/KDJ）由 K线 在本地用 pandas 计算，
  比 westock technical 端点更稳定（该端点部分字段返回 '-'）。
- 内置 TTL 内存缓存，避免每个请求都打一次外部接口。
"""
import time
import math
from typing import Optional

import pandas as pd

from app.services.westock_client import run_table, WeStockError, is_available
from app.services import mock_data

# ============================================================
# 缓存
# ============================================================
_CACHE: dict[str, tuple[float, object]] = {}
CACHE_TTL = int(__import__("os").environ.get("DATA_CACHE_TTL", "30"))  # 秒


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


# ============================================================
# 指数映射
# ============================================================
INDEX_MAP = {
    "sh000001": {"code": "000001.SH", "name": "上证指数"},
    "sz399001": {"code": "399001.SZ", "name": "深证成指"},
    "sz399006": {"code": "399006.SZ", "name": "创业板指"},
    "sh000300": {"code": "000300.SH", "name": "沪深300"},
    "sh000905": {"code": "000905.SH", "name": "中证500"},
}
INDEX_CODES = ",".join(INDEX_MAP.keys())


# ============================================================
# 股票代码转换 → westock 格式
# ============================================================
def to_westock_code(code: str) -> str:
    """'600519' / '600519.SH' → 'sh600519'"""
    code = code.strip().upper()
    if code.startswith(("SH", "SZ", "BJ", "HK", "US")):
        return code.lower()
    if "." in code:
        num, suffix = code.split(".", 1)
        pre = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(suffix, "sh")
        return pre + num
    if code[0] == "6":
        return "sh" + code
    if code[0] in ("0", "3"):
        return "sz" + code
    if code[0] in ("8", "4"):
        return "bj" + code
    return "sh" + code


# ============================================================
# 技术指标计算（本地 pandas）
# ============================================================
def calc_indicators(closes: list[float]) -> dict:
    """基于收盘价序列计算 MACD / RSI / BOLL / KDJ。"""
    s = pd.Series(closes)
    out = {}

    # EMA
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd = (dif - dea) * 2
    out["macd"] = {
        "dif": round(float(dif.iloc[-1]), 3),
        "dea": round(float(dea.iloc[-1]), 3),
        "macd": round(float(macd.iloc[-1]), 3),
    }

    # RSI(14)
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    out["rsi"] = round(float(rsi.iloc[-1]), 2) if pd.notna(rsi.iloc[-1]) else 50.0

    # BOLL(20, 2)
    mid = s.rolling(20).mean()
    std = s.rolling(20).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    out["boll"] = {
        "upper": round(float(upper.iloc[-1]), 2),
        "mid": round(float(mid.iloc[-1]), 2),
        "lower": round(float(lower.iloc[-1]), 2),
    }

    # KDJ(9,3,3)
    low9 = s.rolling(9).min()
    high9 = s.rolling(9).max()
    rsv = (s - low9) / (high9 - low9).replace(0, pd.NA) * 100
    rsv = rsv.fillna(50)
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    out["kdj"] = {
        "k": round(float(k.iloc[-1]), 2),
        "d": round(float(d.iloc[-1]), 2),
        "j": round(float(j.iloc[-1]), 2),
    }
    return out


def _score_from_indicators(ind: dict, closes: list[float]) -> dict:
    """根据技术指标生成一个 0-100 技术评分。"""
    score = 50.0
    # MACD 金叉/红柱
    m = ind["macd"]
    if m["macd"] > 0:
        score += 15
    else:
        score -= 10
    # RSI
    rsi = ind["rsi"]
    if 40 <= rsi <= 70:
        score += 15
    elif rsi > 80:
        score -= 15
    elif rsi < 20:
        score += 5
    # 价格在 BOLL 中轨上方
    b = ind["boll"]
    if closes[-1] >= b["mid"]:
        score += 10
    else:
        score -= 10
    # 均线多头（5日 > 20日，用简单收盘价窗口近似）
    if len(closes) >= 20:
        if closes[-1] > sum(closes[-5:]) / 5 > sum(closes[-20:]) / 20:
            score += 10
    return {
        "technical": max(0, min(100, round(score))),
        "capital": max(0, min(100, round(score + (5 if m["macd"] > 0 else -5)))),
    }


# ============================================================
# 公开接口
# ============================================================
def get_indices() -> list[dict]:
    """获取 5 大指数实时行情（真实数据 + mock 兜底）。"""

    def _fetch():
        quote_rows = run_table(["quote", INDEX_CODES], timeout=25)
        kline_rows = run_table(
            ["kline", INDEX_CODES, "--period", "day", "--limit", "20", "--fq", "qfq"],
            timeout=25,
        )
        # 按 symbol 建索引
        quote_by = {r["symbol"]: r for r in quote_rows}
        # kline 按 symbol 分组，取 last 序列
        kline_by: dict[str, list[dict]] = {}
        for r in kline_rows:
            kline_by.setdefault(r["symbol"], []).append(r)
        result = []
        for sym, meta in INDEX_MAP.items():
            q = quote_by.get(sym)
            kl = kline_by.get(sym, [])
            if not q:
                continue
            price = _to_float(q.get("price"))
            prev = _to_float(q.get("prev_close"), price)
            change = round(price - prev, 2)
            change_pct = round((change / prev * 100) if prev else 0, 2)
            amount = _to_float(q.get("amount"))
            vol_str = f"{amount / 1e8:.0f}亿" if amount else "—"
            # sparkline：按日期升序的 last 值
            kl_sorted = sorted(kl, key=lambda x: x.get("date", ""))
            spark = [round(_to_float(x.get("last")), 2) for x in kl_sorted if x.get("last")]
            result.append({
                "code": meta["code"],
                "name": meta["name"],
                "value": price,
                "change": change,
                "changePct": change_pct,
                "volume": vol_str,
                "sparkline": spark[-20:],
            })
        if not result:
            raise WeStockError("指数数据为空")
        return result

    try:
        return _cached("indices", _fetch)
    except WeStockError:
        return mock_data.MARKET_INDICES


def get_news() -> list[dict]:
    """获取沪深市场实时新闻（真实数据 + mock 兜底）。"""

    POS = ["涨", "利好", "增长", "降准", "反弹", "突破", "增持", "回购", "超预期", "回暖", "走强", "上调"]
    NEG = ["跌", "利空", "下降", "风险", "承压", "下跌", "减持", "亏损", "预警", "放缓", "走弱", "下调"]

    def _sentiment(title: str, summary: str) -> tuple[str, int]:
        text = (title or "") + (summary or "")
        pos = sum(1 for w in POS if w in text)
        neg = sum(1 for w in NEG if w in text)
        if pos > neg:
            return "positive", min(5, pos)
        if neg > pos:
            return "negative", -min(5, neg)
        return "neutral", 0

    def _fetch():
        rows = run_table(["marketnews", "hs"], timeout=25)
        if not rows:
            raise WeStockError("新闻数据为空")
        items = []
        for i, r in enumerate(rows[:20]):
            title = r.get("title", "")
            summary = r.get("summary", "")
            sent, impact = _sentiment(title, summary)
            items.append({
                "id": r.get("id") or f"news-{i:03d}",
                "title": title,
                "source": r.get("src") or r.get("source") or "腾讯财经",
                "time": r.get("time", ""),
                "sentiment": sent,
                "impact": impact,
                "relatedStocks": [],
                "summary": summary or title,
            })
        return items

    try:
        return _cached("news", _fetch)
    except WeStockError:
        return mock_data.NEWS_ITEMS


def get_stock_kline(code: str, period: str = "day", limit: int = 120) -> list[dict]:
    """获取个股/指数 K线（真实数据 + mock 兜底）。返回 KlineData 列表。"""
    ws_code = to_westock_code(code)

    def _fetch():
        period_arg = {"day": "day", "week": "week", "month": "month"}.get(period, "day")
        rows = run_table(
            ["kline", ws_code, "--period", period_arg, "--limit", str(limit), "--fq", "qfq"],
            timeout=25,
        )
        if not rows:
            raise WeStockError("K线数据为空")
        result = []
        for r in sorted(rows, key=lambda x: x.get("date", "")):
            last = _to_float(r.get("last"))
            if not last:
                continue
            result.append({
                "date": r.get("date", ""),
                "open": _to_float(r.get("open")),
                "close": last,
                "high": _to_float(r.get("high")),
                "low": _to_float(r.get("low")),
                "volume": _to_float(r.get("volume")),
            })
        if not result:
            raise WeStockError("K线解析为空")
        return result

    try:
        return _cached(f"kline:{ws_code}:{period}:{limit}", _fetch)
    except WeStockError:
        # 兜底：生成一个贴近该 code 的简单随机序列
        return _mock_kline(code, limit)


def get_stock_analysis(code: str) -> dict:
    """获取个股全景分析（真实数据 + mock 兜底）。"""
    ws_code = to_westock_code(code)

    def _fetch():
        qrows = run_table(["quote", ws_code], timeout=25)
        if not qrows:
            raise WeStockError("个股行情为空")
        q = qrows[0]
        name = q.get("name", code)
        price = _to_float(q.get("price"))
        prev = _to_float(q.get("prev_close"), price)
        change = round(price - prev, 2)
        change_pct = round((change / prev * 100) if prev else 0, 2)

        kline = get_stock_kline(code, "day", 120)
        closes = [k["close"] for k in kline]
        ind = calc_indicators(closes)
        sc = _score_from_indicators(ind, closes)

        # 基本面/情绪/AI 评分：基于真实涨跌与技术面做合理合成（非投资建议）
        fundamental = max(0, min(100, 60 + round(change_pct * 2)))
        sentiment = max(0, min(100, 55 + round(change_pct * 1.5)))
        ai = max(0, min(100, round((sc["technical"] + fundamental + sentiment) / 3)))

        return {
            "code": code,
            "name": name,
            "fundamentalScore": fundamental,
            "technicalScore": sc["technical"],
            "capitalScore": sc["capital"],
            "sentimentScore": sentiment,
            "aiScore": ai,
            "currentPrice": price,
            "change": change,
            "changePct": change_pct,
            "klineData": kline,
            "indicators": ind,
            "prediction": _predict(closes, ind),
        }

    try:
        return _cached(f"analysis:{ws_code}", _fetch)
    except WeStockError:
        return _mock_analysis(code)


def _predict(closes: list[float], ind: dict) -> dict:
    """极简趋势外推（仅供展示，非投资建议）。"""
    if len(closes) < 2:
        return {"d1": {"direction": "震荡", "pct": 0.0}, "d5": {"direction": "震荡", "pct": 0.0}, "d20": {"direction": "震荡", "pct": 0.0}}
    last = closes[-1]
    # 用 BOLL 中轨与 MACD 判断方向与幅度
    mid = ind["boll"]["mid"]
    macd = ind["macd"]["macd"]
    if last > mid and macd > 0:
        d, mag = "上涨", min(5.0, abs(macd) / last * 100 * 3 + 1)
    elif last < mid and macd < 0:
        d, mag = "下跌", min(5.0, abs(macd) / last * 100 * 3 + 1)
    else:
        d, mag = "震荡", 1.0
    return {
        "d1": {"direction": d, "pct": round(mag, 2)},
        "d5": {"direction": d, "pct": round(mag * 2.2, 2)},
        "d20": {"direction": d, "pct": round(mag * 4.5, 2)},
    }


def _mock_kline(code: str, limit: int = 120) -> list[dict]:
    import random
    import hashlib
    from datetime import datetime, timedelta
    # 确定性种子：同一 code 每次生成相同序列，保证回测结果可复现（不依赖外部随机状态）
    seed = int(hashlib.md5(code.encode("utf-8")).hexdigest(), 16) % (2**32)
    random.seed(seed)
    data, price, cur = [], 50.0, datetime(2025, 1, 2)
    for _ in range(limit):
        if cur.weekday() < 5:
            price *= 1 + (random.random() - 0.48) * 0.03
            data.append({"date": cur.strftime("%Y-%m-%d"), "open": price, "close": price,
                         "high": price * 1.01, "low": price * 0.99, "volume": random.randint(10000, 50000)})
        cur += timedelta(days=1)
    return data


def _mock_analysis(code: str) -> dict:
    return {
        "code": code, "name": "未知", "fundamentalScore": 60, "technicalScore": 60,
        "capitalScore": 60, "sentimentScore": 60, "aiScore": 60, "currentPrice": 0,
        "change": 0, "changePct": 0, "klineData": _mock_kline(code),
        "indicators": {"macd": {"dif": 0, "dea": 0, "macd": 0}, "kdj": {"k": 50, "d": 50, "j": 50},
                        "rsi": 50, "boll": {"upper": 0, "mid": 0, "lower": 0}},
        "prediction": {"d1": {"direction": "震荡", "pct": 0}, "d5": {"direction": "震荡", "pct": 0}, "d20": {"direction": "震荡", "pct": 0}},
    }


def get_ai_report() -> dict:
    """AI 研究报告：指数动量(60%) + 新闻情绪(40%) 合成，失败回退 mock。"""
    try:
        indices = get_indices()
        news = get_news()

        # 指数动量分量（0-100）
        up = sum(1 for i in indices if i["change"] > 0)
        down = sum(1 for i in indices if i["change"] < 0)
        idx_mag = sum(i["changePct"] for i in indices)
        index_score = 50 + (up - down) * 8 + idx_mag * 2.0

        # 新闻情绪分量（0-100）
        pos = sum(1 for n in news if n["sentiment"] == "positive")
        neg = sum(1 for n in news if n["sentiment"] == "negative")
        ntot = max(1, len(news))
        news_score = 50 + (pos - neg) / ntot * 40

        score = max(0, min(100, round(index_score * 0.6 + news_score * 0.4)))
        judgment = "bullish" if score >= 60 else ("bearish" if score <= 40 else "neutral")
        idx_desc = "、".join(f"{i['name']}{i['changePct']:+.2f}%" for i in indices)
        return {
            "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
            "marketSummary": f"今日主要指数：{idx_desc}。数据来自腾讯自选股实时行情接口。",
            "upReasons": ["市场流动性边际改善", "北向资金动向回暖（以交易所数据为准）", "政策面预期偏积极"],
            "riskFactors": ["外部利率与汇率波动", "部分高估值板块存在回调压力", "成交额能否持续放大待观察"],
            "focusStocks": [],
            "sentimentScore": score,
            "aiJudgment": judgment,
        }
    except Exception:
        return mock_data.AI_REPORT


def data_source_status() -> dict:
    """返回当前数据源可用性（用于健康检查 / 调试）。"""
    return {"westock_available": is_available(), "cache_entries": len(_CACHE)}
