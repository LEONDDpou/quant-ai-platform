"""市场温度计服务 — 估值/情绪/资金/技术四维综合评分（0-100）。

数据源：
  - westock-data kline  → 指数K线（技术指标计算）
  - westock-data asfund → 主力资金流向（资金温度）
  - westock-data quote  → 指数快照（日内涨跌）
  - 新闻情绪数据        → 情绪温度

四维权重（可调）：
  估值 30% · 情绪 25% · 资金 25% · 技术 20%
"""

import time
import math
from datetime import date, timedelta
from app.services.westock_client import run_table, WeStockError, _run as westock_run_raw

CACHE: dict[str, tuple[float, object]] = {}
CACHE_TTL = 120  # 温度数据缓存 2 分钟


def _cached(key: str, fetcher, ttl: int = CACHE_TTL):
    now = time.time()
    if key in CACHE:
        ts, val = CACHE[key]
        if now - ts < ttl:
            return val
    val = fetcher()
    CACHE[key] = (now, val)
    return val


def _to_float(v, default=0.0):
    try:
        if v in (None, "", "-", "—"):
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


# ============================================================
# 数据获取
# ============================================================
def _get_index_kline(symbol: str = "sh000001", limit: int = 120):
    """获取指数日K线，返回 [{date, open, close, high, low, volume}, ...]"""
    try:
        raw = westock_run_raw(["kline", symbol, "--period", "day", "--limit", str(limit), "--fq", "qfq"], timeout=20)
        return _parse_kline_markdown(raw)
    except Exception:
        return []


def _parse_kline_markdown(raw: str) -> list[dict]:
    """解析 westock-data kline 输出的 Markdown 表格。"""
    rows = []
    lines = raw.strip().split("\n")
    header_found = False
    cols = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("|--"):
            continue
        parts = [c.strip() for c in line.split("|") if c.strip()]
        if not parts:
            continue
        # 找表头
        if not header_found and any(k in parts for k in ("日期", "date", "开盘")):
            cols = parts
            header_found = True
            continue
        if header_found:
            row = {}
            for i, c in enumerate(parts):
                if i < len(cols):
                    row[cols[i]] = c
            if row:
                rows.append(row)
    return rows


def _get_index_quote(symbols: str = "sh000001,sz399001,sz399006"):
    """获取指数快照。"""
    try:
        rows = run_table(["quote", symbols], timeout=15)
        return rows
    except WeStockError:
        return []


def _get_capital_flow():
    """获取主力资金流向（上证）。"""
    try:
        rows = run_table(["asfund", "sh000001"], timeout=15)
        if rows:
            r = rows[0]
            return {
                "mainNetFlow": _to_float(r.get("MainNetFlow")),
                "mainNetFlow5d": _to_float(r.get("MainNetFlow5D")),
                "mainNetFlow20d": _to_float(r.get("MainNetFlow20D")),
            }
    except WeStockError:
        pass
    return {"mainNetFlow": 0, "mainNetFlow5d": 0, "mainNetFlow20d": 0}


def _get_news_sentiment() -> dict:
    """聚合新闻面情绪指标。"""
    from app.services import data_provider as dp
    try:
        news = dp.get_news()
        pos = sum(1 for n in news if n.get("sentiment") == "positive")
        neg = sum(1 for n in news if n.get("sentiment") == "negative")
        total = max(len(news), 1)
        return {
            "positiveRatio": pos / total,
            "negativeRatio": neg / total,
            "totalNews": len(news),
        }
    except Exception:
        return {"positiveRatio": 0.5, "negativeRatio": 0.3, "totalNews": 0}


# ============================================================
# RSI 计算
# ============================================================
def _calc_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    # Wilder smoothing
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


# ============================================================
# 四维温度计算
# ============================================================
# 辅助：提取收盘价序列
# ============================================================
def _extract_closes(index_kline: list[dict]) -> list[float]:
    """从K线数据中提取有效收盘价序列（跳过 --- 分隔行）。"""
    closes = []
    for r in index_kline:
        # 跳过分隔行
        val = r.get("收盘", r.get("close", r.get("last", "")))
        if val in ("", "---", None):
            continue
        f = _to_float(val)
        if f > 0:
            closes.append(f)
    return closes


# ============================================================
def _calc_valuation_temperature(index_kline: list[dict]) -> dict:
    """估值温度：基于指数价格相对于均线位置 + 布林带位置。"""
    closes = _extract_closes(index_kline)
    if len(closes) < 20:
        return {"score": 50, "label": "正常", "detail": "数据不足"}

    latest = closes[-1]
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else ma20
    ma250 = sum(closes[-250:]) / 250 if len(closes) >= 250 else ma60

    # 偏离20日均线幅度
    dev_ma20 = (latest - ma20) / ma20 * 100
    # 相对于一年MA的位置
    dev_ma250 = (latest - ma250) / ma250 * 100 if ma250 > 0 else 0

    # 布林带位置
    std20 = 0
    if len(closes) >= 20:
        m = ma20
        std20 = math.sqrt(sum((c - m) ** 2 for c in closes[-20:]) / 20)
    bb_upper = ma20 + 2 * std20 if std20 > 0 else latest * 1.1
    bb_lower = ma20 - 2 * std20 if std20 > 0 else latest * 0.9
    if bb_upper > bb_lower:
        bb_position = (latest - bb_lower) / (bb_upper - bb_lower) * 100
    else:
        bb_position = 50

    # 综合估值温度：偏离越大越贵
    # dev_ma250: -10% → 温度约20, +10% → 温度约80
    val_score = 50 + dev_ma250 * 3
    # 布林带位置修正
    val_score = val_score * 0.7 + bb_position * 0.3
    val_score = max(0, min(100, val_score))

    if val_score < 30:
        label = "低估"
    elif val_score < 50:
        label = "偏低"
    elif val_score < 70:
        label = "正常"
    elif val_score < 85:
        label = "偏高"
    else:
        label = "高估"

    return {
        "score": round(val_score, 1),
        "label": label,
        "detail": {
            "latestPrice": round(latest, 2),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
            "ma250": round(ma250, 2),
            "devMa20Pct": round(dev_ma20, 1),
            "devMa250Pct": round(dev_ma250, 1),
            "bbPosition": round(bb_position, 1),
        },
    }


def _calc_sentiment_temperature(index_quotes: list[dict], news: dict) -> dict:
    """情绪温度：基于新闻正负面比例 + 指数日内表现。"""
    pos = news.get("positiveRatio", 0.5)
    neg = news.get("negativeRatio", 0.3)

    # 新闻情绪：正面多 → 温度高
    sentiment_score = 50 + (pos - neg) * 80
    sentiment_score = max(0, min(100, sentiment_score))

    # 指数涨跌补充
    index_chg = 0
    if index_quotes:
        for q in index_quotes:
            chg = _to_float(q.get("zdf", q.get("涨跌幅", 0)))
            index_chg = chg  # 用第一个指数
            break

    # 涨跌幅对情绪的贡献
    index_bonus = index_chg * 2
    sentiment_score = sentiment_score * 0.7 + (50 + index_bonus) * 0.3
    sentiment_score = max(0, min(100, sentiment_score))

    if sentiment_score < 30:
        label = "悲观"
    elif sentiment_score < 50:
        label = "偏冷"
    elif sentiment_score < 70:
        label = "正常"
    elif sentiment_score < 85:
        label = "乐观"
    else:
        label = "狂热"

    return {
        "score": round(sentiment_score, 1),
        "label": label,
        "detail": {
            "positiveRatio": round(pos, 2),
            "negativeRatio": round(neg, 2),
            "totalNews": news.get("totalNews", 0),
            "indexChangePct": round(index_chg, 2),
        },
    }


def _calc_capital_temperature(capital_flow: dict) -> dict:
    """资金温度：基于主力资金净流向。"""
    main = capital_flow.get("mainNetFlow", 0)
    main5 = capital_flow.get("mainNetFlow5d", 0)
    main20 = capital_flow.get("mainNetFlow20d", 0)

    # 归一化：假设 ±50亿 为极端区间
    norm_main = max(-50, min(50, main / 1e8))  # 亿
    cap_score = 50 + norm_main * 1.0
    # 5日趋势修正
    norm_5 = max(-50, min(50, main5 / 1e8))
    cap_score = cap_score * 0.6 + (50 + norm_5 * 0.6) * 0.4
    cap_score = max(0, min(100, cap_score))

    if cap_score < 30:
        label = "流出"
    elif cap_score < 50:
        label = "偏流出"
    elif cap_score < 70:
        label = "偏流入"
    else:
        label = "流入"

    return {
        "score": round(cap_score, 1),
        "label": label,
        "detail": {
            "mainNetFlow": round(main / 1e8, 2),
            "mainNetFlow5d": round(main5 / 1e8, 2),
            "mainNetFlow20d": round(main20 / 1e8, 2),
        },
    }


def _calc_technical_temperature(index_kline: list[dict]) -> dict:
    """技术温度：基于 RSI + MACD + 均线排列。"""
    closes = _extract_closes(index_kline)
    if len(closes) < 26:
        return {"score": 50, "label": "正常", "detail": "数据不足"}

    # RSI
    rsi = _calc_rsi(closes, 14)

    # 均线排列
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else ma5
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else ma5
    ma_bull = 1 if closes[-1] > ma5 > ma10 > ma20 else 0
    ma_bear = 1 if closes[-1] < ma5 < ma10 < ma20 else 0

    # 技术温度综合
    # RSI: 50 → 温度 50; RSI 30 → 温度 25; RSI 70 → 温度 75
    rsi_score = max(0, min(100, rsi * 0.5 + 25))
    # 均线排列
    if ma_bull:
        ma_bonus = 15
    elif ma_bear:
        ma_bonus = -15
    else:
        ma_bonus = 0

    tech_score = rsi_score * 0.6 + (50 + ma_bonus) * 0.4
    tech_score = max(0, min(100, tech_score))

    if tech_score < 30:
        label = "偏弱"
    elif tech_score < 50:
        label = "正常偏弱"
    elif tech_score < 70:
        label = "正常偏强"
    else:
        label = "偏强"

    return {
        "score": round(tech_score, 1),
        "label": label,
        "detail": {
            "rsi": round(rsi, 1),
            "ma5": round(ma5, 2),
            "ma20": round(ma20, 2),
            "maAlignment": "多头排列" if ma_bull else ("空头排列" if ma_bear else "交织"),
        },
    }


# ============================================================
# 公开接口
# ============================================================
def get_market_temperature(force: bool = False) -> dict:
    """获取综合市场温度（0-100）及四维拆解。"""

    def _fetch():
        # 并行取数据
        kline = _get_index_kline("sh000001", 120)
        quotes = _get_index_quote("sh000001,sz399001,sz399006")
        cap_flow = _get_capital_flow()
        news = _get_news_sentiment()

        valuation = _calc_valuation_temperature(kline)
        sentiment = _calc_sentiment_temperature(quotes, news)
        capital = _calc_capital_temperature(cap_flow)
        technical = _calc_technical_temperature(kline)

        # 综合温度：加权平均
        weights = {"valuation": 0.30, "sentiment": 0.25, "capital": 0.25, "technical": 0.20}
        composite = (
            valuation["score"] * weights["valuation"]
            + sentiment["score"] * weights["sentiment"]
            + capital["score"] * weights["capital"]
            + technical["score"] * weights["technical"]
        )
        composite = round(composite, 1)

        # 风险等级
        if composite < 30:
            risk_level = "extreme_low"
            risk_label = "极度悲观（抄底区间）"
        elif composite < 50:
            risk_level = "low"
            risk_label = "偏冷（逐步建仓）"
        elif composite < 70:
            risk_level = "medium"
            risk_label = "正常（持仓为主）"
        elif composite < 85:
            risk_level = "high"
            risk_label = "偏热（逐步减仓）"
        else:
            risk_level = "extreme_high"
            risk_label = "过热（减仓/空仓）"

        result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "date": date.today().isoformat(),
            "score": composite,
            "riskLevel": risk_level,
            "riskLabel": risk_label,
            "valuation": valuation,
            "sentiment": sentiment,
            "capital": capital,
            "technical": technical,
            "weights": weights,
        }

        # 持久化到 DB
        _save_temperature(result)
        return result

    cache_key = "market_temperature"
    if force:
        CACHE.pop(cache_key, None)
    return _cached(cache_key, _fetch)


def _save_temperature(result: dict):
    """将温度数据落库（用于历史查询）。"""
    try:
        from app.db.database import SessionLocal
        from app.db.models import MarketTemperature
        db = SessionLocal()
        try:
            today = date.today()
            existing = db.query(MarketTemperature).filter(MarketTemperature.date == today).first()
            if existing:
                existing.score = result["score"]
                existing.valuation = result["valuation"]["score"]
                existing.sentiment = result["sentiment"]["score"]
                existing.capital = result["capital"]["score"]
                existing.technical = result["technical"]["score"]
                existing.risk_level = result["riskLevel"]
            else:
                db.add(MarketTemperature(
                    date=today,
                    score=result["score"],
                    valuation=result["valuation"]["score"],
                    sentiment=result["sentiment"]["score"],
                    capital=result["capital"]["score"],
                    technical=result["technical"]["score"],
                    risk_level=result["riskLevel"],
                ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[Temperature] DB save failed: {e}")


def get_temperature_history(days: int = 30) -> list[dict]:
    """获取历史温度时间序列。"""
    try:
        from app.db.database import SessionLocal
        from app.db.models import MarketTemperature
        db = SessionLocal()
        try:
            since = date.today() - timedelta(days=days)
            rows = (
                db.query(MarketTemperature)
                .filter(MarketTemperature.date >= since)
                .order_by(MarketTemperature.date.asc())
                .all()
            )
            return [
                {
                    "date": r.date.isoformat() if isinstance(r.date, date) else str(r.date),
                    "score": r.score,
                    "valuation": r.valuation,
                    "sentiment": r.sentiment,
                    "capital": r.capital,
                    "technical": r.technical,
                    "riskLevel": r.risk_level,
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        print(f"[Temperature] History query failed: {e}")
        return []
