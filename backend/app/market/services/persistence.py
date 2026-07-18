"""行情数据持久化（需求 6：PostgreSQL 存储）。

将实时行情、历史 K 线、AI 评分、市场宽度快照写入异步 PostgreSQL（或开发态 SQLite）。
批量写入 + 异常吞掉仅告警，避免阻塞实时推送主链路。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..core.db import session_scope
from ..core.models import AIScore, KlineBar, MarketBreadth, RealtimeQuote
from ..sources.base import Quote

logger = logging.getLogger(__name__)


def _quote_row(q: Quote) -> dict:
    ts = datetime.fromtimestamp(q.ts, tz=timezone.utc) if q.ts else datetime.utcnow()
    return {
        "code": q.code, "name": q.name, "price": q.price, "change": q.change,
        "change_pct": q.change_pct, "volume": q.volume, "amount": q.amount,
        "turnover": q.turnover, "pe": q.pe, "pb": q.pb,
        "total_mv": q.total_mv, "float_mv": q.float_mv,
        "source": q.source, "ts": ts,
    }


def _parse_dt(s: str) -> datetime:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.utcnow()


async def save_quotes(quotes: list[Quote]) -> int:
    if not quotes:
        return 0
    try:
        rows = [_quote_row(q) for q in quotes]
        async with session_scope() as s:
            s.add_all([RealtimeQuote(**r) for r in rows])
            await s.commit()
        return len(rows)
    except Exception as e:  # noqa: BLE001
        logger.warning("[persist] 实时行情落库失败: %s", e)
        return 0


async def save_klines(code: str, period: str, bars: list[dict]) -> int:
    if not bars:
        return 0
    try:
        async with session_scope() as s:
            for b in bars:
                s.add(KlineBar(
                    code=code, period=period, dt=_parse_dt(b.get("dt", "")),
                    open=b.get("open", 0.0), high=b.get("high", 0.0),
                    low=b.get("low", 0.0), close=b.get("close", 0.0),
                    volume=b.get("volume", 0), amount=b.get("amount", 0.0),
                ))
            await s.commit()
        return len(bars)
    except Exception as e:  # noqa: BLE001
        logger.warning("[persist] K线落库失败 %s/%s: %s", code, period, e)
        return 0


async def save_ai_scores(scored: list[dict]) -> int:
    if not scored:
        return 0
    try:
        async with session_scope() as s:
            for it in scored:
                s.add(AIScore(
                    code=it["code"], name=it.get("name", ""),
                    score=it["score"], tech_score=it.get("techScore", 0.0),
                    fund_score=it.get("fundScore", 0.0),
                    sentiment_score=it.get("sentimentScore", 0.0),
                    momentum=it.get("momentum", 0.0),
                    volatility=it.get("volatility", 0.0),
                    risk_level=it.get("riskLevel", ""),
                ))
            await s.commit()
        return len(scored)
    except Exception as e:  # noqa: BLE001
        logger.warning("[persist] AI评分落库失败: %s", e)
        return 0


async def save_breadth(snapshot: dict) -> int:
    agg = (snapshot or {}).get("aggregate") or {}
    if not agg.get("total"):
        return 0
    try:
        async with session_scope() as s:
            s.add(MarketBreadth(
                trade_date=snapshot.get("date") or datetime.utcnow().strftime("%Y-%m-%d"),
                total=agg.get("total", 0), up=agg.get("upCount", 0),
                down=agg.get("downCount", 0), flat=agg.get("flatCount", 0),
                limit_up=agg.get("limitUp", 0), limit_down=agg.get("limitDown", 0),
                northbound=snapshot.get("northbound") or 0.0,
            ))
            await s.commit()
        return 1
    except Exception as e:  # noqa: BLE001
        logger.warning("[persist] 市场宽度落库失败: %s", e)
        return 0
