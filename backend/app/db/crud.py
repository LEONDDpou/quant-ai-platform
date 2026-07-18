"""CRUD 操作 — 持久化各业务对象。

约定：
- 每个函数独立开/关 Session（不依赖外部传入），便于在路由或 asyncio.to_thread 中安全调用。
- 所有写入包 try/except，DB 异常仅打印日志并吞掉，绝不中断上层业务（行情/报告照常返回）。
- 读取失败返回空列表 / None，由调用方决定兜底。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import desc

from app.db.database import SessionLocal
from app.db import models


def _safe(func):
    """装饰器：吞掉 DB 异常，保证上层不崩。"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            print(f"[DB:{func.__name__}] error: {type(e).__name__}: {e}")
            return None
    return wrapper


# ============================================================
# AI 报告
# ============================================================
@_safe
def save_ai_report(report: dict, llm_enabled: bool, model: str) -> int | None:
    db = SessionLocal()
    try:
        obj = models.AIReport(
            date=report.get("date"),
            market_summary=report.get("marketSummary", ""),
            up_reasons=report.get("upReasons", []),
            risk_factors=report.get("riskFactors", []),
            focus_stocks=report.get("focusStocks", []),
            sentiment_score=report.get("sentimentScore", 50),
            ai_judgment=report.get("aiJudgment", "neutral"),
            outlook=report.get("outlook", ""),
            llm_enabled=llm_enabled,
            model=model,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj.id
    finally:
        db.close()


@_safe
def get_latest_ai_report() -> Optional[dict]:
    db = SessionLocal()
    try:
        obj = db.query(models.AIReport).order_by(desc(models.AIReport.created_at)).first()
        if not obj:
            return None
        return _report_to_dict(obj)
    finally:
        db.close()


@_safe
def get_ai_report_history(limit: int = 20) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.AIReport)
            .order_by(desc(models.AIReport.created_at))
            .limit(limit)
            .all()
        )
        return [_report_to_dict(r) for r in rows]
    finally:
        db.close()


def _report_to_dict(o: models.AIReport) -> dict:
    return {
        "id": o.id,
        "date": o.date,
        "marketSummary": o.market_summary,
        "upReasons": o.up_reasons or [],
        "riskFactors": o.risk_factors or [],
        "focusStocks": o.focus_stocks or [],
        "sentimentScore": o.sentiment_score,
        "aiJudgment": o.ai_judgment,
        "outlook": o.outlook or "",
        "llmEnabled": bool(o.llm_enabled),
        "model": o.model,
        "createdAt": o.created_at.isoformat() if o.created_at else "",
    }


# ============================================================
# 回测结果
# ============================================================
@_safe
def save_backtest_result(result: dict) -> int | None:
    db = SessionLocal()
    try:
        obj = models.BacktestResult(
            strategy_name=result.get("strategyName", ""),
            symbol=result.get("symbol") or result.get("strategyName", ""),
            start_date=result.get("startDate", ""),
            end_date=result.get("endDate", ""),
            initial_capital=float(result.get("initialCapital", 0) or 0),
            total_return=float(result.get("totalReturn", 0) or 0),
            annualized_return=float(result.get("annualizedReturn", 0) or 0),
            sharpe_ratio=float(result.get("sharpeRatio", 0) or 0),
            max_drawdown=float(result.get("maxDrawdown", 0) or 0),
            win_rate=float(result.get("winRate", 0) or 0),
            total_trades=int(result.get("totalTrades", 0) or 0),
            avg_hold_days=float(result.get("avgHoldDays", 0) or 0),
            equity_curve=result.get("equityCurve", []),
            trades=result.get("trades", []),
            data_source=result.get("dataSource", "unknown"),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj.id
    finally:
        db.close()


@_safe
def get_backtest_history(limit: int = 20) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.BacktestResult)
            .order_by(desc(models.BacktestResult.created_at))
            .limit(limit)
            .all()
        )
        return [_backtest_to_dict(r) for r in rows]
    finally:
        db.close()


def _backtest_to_dict(o: models.BacktestResult) -> dict:
    return {
        "id": o.id,
        "strategyName": o.strategy_name,
        "symbol": o.symbol,
        "startDate": o.start_date,
        "endDate": o.end_date,
        "totalReturn": o.total_return,
        "annualizedReturn": o.annualized_return,
        "sharpeRatio": o.sharpe_ratio,
        "maxDrawdown": o.max_drawdown,
        "winRate": o.win_rate,
        "totalTrades": o.total_trades,
        "dataSource": o.data_source,
        "createdAt": o.created_at.isoformat() if o.created_at else "",
    }


# ============================================================
# 新闻（去重 upsert）
# ============================================================
@_safe
def upsert_news_items(items: list[dict]) -> int:
    """批量写入新闻，按 unique_key 去重。返回新增条数。

    逐条提交 + 捕获唯一约束冲突，避免整批因重复 key 回滚。
    """
    from sqlalchemy.exc import IntegrityError

    db = SessionLocal()
    added = 0
    try:
        for it in items:
            key = f"{it.get('title','')}|{it.get('time','')}"[:600]
            exists = (
                db.query(models.NewsItem)
                .filter(models.NewsItem.unique_key == key)
                .first()
            )
            if exists:
                continue
            db.add(
                models.NewsItem(
                    unique_key=key,
                    title=it.get("title", "")[:500],
                    source=it.get("source", "")[:100],
                    time=it.get("time", "")[:50],
                    sentiment=it.get("sentiment", "neutral"),
                    impact=int(it.get("impact", 0) or 0),
                    summary=it.get("summary", "")[:2000],
                )
            )
            try:
                db.commit()
                added += 1
            except IntegrityError:
                db.rollback()  # 并发/重复，跳过
        return added
    finally:
        db.close()


@_safe
def get_news_history(limit: int = 50) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.NewsItem)
            .order_by(desc(models.NewsItem.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "title": r.title,
                "source": r.source,
                "time": r.time,
                "sentiment": r.sentiment,
                "impact": r.impact,
                "summary": r.summary,
            }
            for r in rows
        ]
    finally:
        db.close()


# ============================================================
# 行情快照（WebSocket 落库）
# ============================================================
@_safe
def save_snapshot(payload: dict) -> int | None:
    db = SessionLocal()
    try:
        obj = models.MarketSnapshot(payload=payload)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj.id
    finally:
        db.close()


@_safe
def get_latest_snapshot() -> Optional[dict]:
    db = SessionLocal()
    try:
        obj = (
            db.query(models.MarketSnapshot)
            .order_by(desc(models.MarketSnapshot.ts))
            .first()
        )
        if not obj:
            return None
        return {
            "id": obj.id,
            "ts": obj.ts.isoformat() if obj.ts else "",
            "payload": obj.payload or {},
        }
    finally:
        db.close()


@_safe
def count_snapshots() -> int:
    db = SessionLocal()
    try:
        return db.query(models.MarketSnapshot).count()
    finally:
        db.close()


# ============================================================
# 策略（策略中心持久化）
# ============================================================
@_safe
def save_or_update_strategy(s: dict) -> None:
    db = SessionLocal()
    try:
        existing = db.query(models.Strategy).filter(models.Strategy.id == s["id"]).first()
        if existing:
            existing.name = s.get("name", existing.name)
            existing.type = s.get("type", existing.type)
            existing.pool = s.get("pool", existing.pool)
            existing.status = s.get("status", existing.status)
            existing.description = s.get("description", existing.description)
            existing.params = s.get("params", existing.params)
            existing.metrics = s.get("metrics", existing.metrics)
            existing.updated_at = datetime.utcnow()
        else:
            db.add(
                models.Strategy(
                    id=s["id"],
                    name=s.get("name", ""),
                    type=s.get("type", ""),
                    pool=s.get("pool", ""),
                    status=s.get("status", "stopped"),
                    description=s.get("description", ""),
                    params=s.get("params"),
                    metrics=s.get("metrics"),
                )
            )
        db.commit()
    finally:
        db.close()


@_safe
def get_all_strategies() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(models.Strategy).order_by(models.Strategy.created_at).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "pool": r.pool,
                "status": r.status,
                "description": r.description,
                "params": r.params,
                "metrics": r.metrics,
                "createdAt": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]
    finally:
        db.close()
