"""预警引擎 — 四类预警：技术信号 / 资金异动 / 事件驱动 / 风控。

设计要点：
  - 规则驱动，阈值可配置
  - WebSocket 推送 + 数据库持久化
  - 冷却机制：同一股票同类型预警 N 分钟内不重复
"""

import time
import datetime
import json
from typing import Optional

from app.db.database import SessionLocal
from app.db.models import Alert, AlertRule

# 默认预警规则（前端可覆盖）
DEFAULT_RULES = {
    "technical": {
        "rsi_overbought": {"threshold": 75, "cooldown_min": 10},
        "rsi_oversold": {"threshold": 25, "cooldown_min": 10},
        "volume_spike": {"threshold": 2.5, "cooldown_min": 15},  # 量比 > 2.5
        "price_breakout": {"threshold": 5.0, "cooldown_min": 20},  # 涨幅 > 5%
    },
    "capital": {
        "main_outflow": {"threshold": -500_000_000, "cooldown_min": 30},  # 主力净流出 > 5亿
        "main_inflow": {"threshold": 800_000_000, "cooldown_min": 30},   # 主力净流入 > 8亿
        "northbound_outflow": {"threshold": -1_000_000_000, "cooldown_min": 60},
    },
    "event": {
        "sentiment_reversal": {"threshold": 0.6, "cooldown_min": 30},  # 情绪突变
        "breaking_news": {"threshold": 1, "cooldown_min": 10},         # 突发新闻
    },
    "risk": {
        "drawdown_warning": {"threshold": -8.0, "cooldown_min": 60},   # 回撤超 8%
        "concentration_warning": {"threshold": 30.0, "cooldown_min": 120},  # 单票占比超30%
    },
}


# ============================================================
# 规则加载
# ============================================================
def get_alert_rules() -> dict:
    """加载预警规则（DB优先，不存在则使用默认规则）。"""
    try:
        db = SessionLocal()
        try:
            rows = db.query(AlertRule).filter(AlertRule.enabled == True).all()
            if rows:
                rules = {}
                for r in rows:
                    rules.setdefault(r.type, {})[r.name] = r.condition
                return rules
        finally:
            db.close()
    except Exception:
        pass
    return DEFAULT_RULES


# ============================================================
# 预警检查
# ============================================================
def check_technical_alerts(context: dict[dict]) -> list[dict]:
    """技术信号预警检查。"""
    alerts = []
    rules = get_alert_rules().get("technical", DEFAULT_RULES["technical"])

    for code, data in context.items():
        rsi = data.get("rsi", 50)
        volume_ratio = data.get("volumeRatio", 1.0)
        change_pct = data.get("changePct", 0)

        if rsi > rules.get("rsi_overbought", {}).get("threshold", 75):
            if not _is_duplicate(code, "technical", "rsi_overbought"):
                alerts.append({
                    "type": "technical",
                    "severity": "warning",
                    "code": code,
                    "title": f"{data.get('name', code)} RSI超买",
                    "message": f"RSI {rsi:.1f}，处于超买区间，注意回调风险",
                    "trigger_condition": f"RSI > {rules['rsi_overbought']['threshold']}",
                })

        if rsi < rules.get("rsi_oversold", {}).get("threshold", 25):
            if not _is_duplicate(code, "technical", "rsi_oversold"):
                alerts.append({
                    "type": "technical",
                    "severity": "info",
                    "code": code,
                    "title": f"{data.get('name', code)} RSI超卖",
                    "message": f"RSI {rsi:.1f}，处于超卖区间，关注反弹机会",
                    "trigger_condition": f"RSI < {rules['rsi_oversold']['threshold']}",
                })

        if volume_ratio > rules.get("volume_spike", {}).get("threshold", 2.5):
            if not _is_duplicate(code, "technical", "volume_spike"):
                alerts.append({
                    "type": "technical",
                    "severity": "info",
                    "code": code,
                    "title": f"{data.get('name', code)} 放量异动",
                    "message": f"量比 {volume_ratio:.1f}，成交显著放大",
                    "trigger_condition": f"量比 > {rules['volume_spike']['threshold']}",
                })

    return alerts


def check_capital_alerts(capital_data: dict) -> list[dict]:
    """资金异动预警检查。"""
    alerts = []
    rules = get_alert_rules().get("capital", DEFAULT_RULES["capital"])

    main_flow = capital_data.get("mainNetFlow", 0)

    if main_flow < rules.get("main_outflow", {}).get("threshold", -5e8):
        if not _is_duplicate("market", "capital", "main_outflow"):
            alerts.append({
                "type": "capital",
                "severity": "warning",
                "code": "market",
                "title": "主力资金大幅流出",
                "message": f"主力资金净流出 {main_flow/1e8:.1f} 亿，市场承压",
                "trigger_condition": f"主力净流出 > {abs(rules['main_outflow']['threshold'])/1e8:.0f}亿",
            })

    if main_flow > rules.get("main_inflow", {}).get("threshold", 8e8):
        if not _is_duplicate("market", "capital", "main_inflow"):
            alerts.append({
                "type": "capital",
                "severity": "info",
                "code": "market",
                "title": "主力资金大幅流入",
                "message": f"主力资金净流入 {main_flow/1e8:.1f} 亿，市场积极",
                "trigger_condition": f"主力净流入 > {rules['main_inflow']['threshold']/1e8:.0f}亿",
            })

    return alerts


def check_event_alerts(news_sentiment_change: Optional[float] = None) -> list[dict]:
    """事件驱动预警。"""
    alerts = []
    if news_sentiment_change is not None and abs(news_sentiment_change) > 0.3:
        direction = "恶化" if news_sentiment_change < 0 else "好转"
        if not _is_duplicate("market", "event", "sentiment_shift"):
            alerts.append({
                "type": "event",
                "severity": "warning" if news_sentiment_change < 0 else "info",
                "code": "market",
                "title": f"市场情绪急剧{direction}",
                "message": f"情绪指标变化 {news_sentiment_change:+.2f}，注意市场风向变化",
                "trigger_condition": f"情绪突变 {news_sentiment_change:+.2f}",
            })
    return alerts


def check_risk_alerts(portfolio_context: Optional[dict] = None) -> list[dict]:
    """风控预警检查。"""
    alerts = []
    rules = get_alert_rules().get("risk", DEFAULT_RULES["risk"])
    if not portfolio_context:
        return alerts

    drawdown = portfolio_context.get("drawdown", 0)
    if drawdown < rules.get("drawdown_warning", {}).get("threshold", -8):
        if not _is_duplicate("portfolio", "risk", "drawdown"):
            alerts.append({
                "type": "risk",
                "severity": "critical",
                "code": "portfolio",
                "title": f"组合回撤预警：{drawdown:.1f}%",
                "message": f"当前最大回撤 {drawdown:.1f}%，超过预警线。建议检查持仓并考虑减仓.",
                "trigger_condition": f"回撤 > {abs(rules['drawdown_warning']['threshold'])}%",
            })

    max_concentration = portfolio_context.get("maxConcentration", 0)
    if max_concentration > rules.get("concentration_warning", {}).get("threshold", 30):
        if not _is_duplicate("portfolio", "risk", "concentration"):
            alerts.append({
                "type": "risk",
                "severity": "warning",
                "code": "portfolio",
                "title": f"持仓集中度预警：{max_concentration:.1f}%",
                "message": f"单一品种占比 {max_concentration:.1f}%，超过集中度上限，建议分散持仓。",
                "trigger_condition": f"单票占比 > {rules['concentration_warning']['threshold']}%",
            })

    return alerts


# ============================================================
# 去重冷却
# ============================================================
_DEDUP_CACHE: dict[str, float] = {}


def _is_duplicate(code: str, alert_type: str, rule_name: str) -> bool:
    """检查是否在冷却期内。"""
    key = f"{code}|{alert_type}|{rule_name}"
    now = time.time()
    rules = get_alert_rules().get(alert_type, {})
    cooldown = rules.get(rule_name, {}).get("cooldown_min", 5) * 60

    if key in _DEDUP_CACHE:
        if now - _DEDUP_CACHE[key] < cooldown:
            return True
    _DEDUP_CACHE[key] = now
    return False


# ============================================================
# 综合巡检 + 持久化
# ============================================================
def run_alert_scan(
    technical_context: Optional[dict] = None,
    capital_data: Optional[dict] = None,
    sentiment_change: Optional[float] = None,
    portfolio_context: Optional[dict] = None,
) -> list[dict]:
    """运行全量预警扫描，返回触发预警列表并持久化。"""
    all_alerts = []

    if technical_context:
        all_alerts.extend(check_technical_alerts(technical_context))
    if capital_data:
        all_alerts.extend(check_capital_alerts(capital_data))
    all_alerts.extend(check_event_alerts(sentiment_change))
    if portfolio_context:
        all_alerts.extend(check_risk_alerts(portfolio_context))

    # 持久化
    _save_alerts(all_alerts)

    return all_alerts


def _save_alerts(alerts: list[dict]):
    """预警持久化。"""
    if not alerts:
        return
    try:
        db = SessionLocal()
        try:
            for a in alerts:
                db.add(Alert(
                    type=a["type"],
                    severity=a["severity"],
                    code=a.get("code", ""),
                    title=a["title"],
                    message=a["message"],
                    trigger_condition=a.get("trigger_condition", ""),
                ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[Alert] DB save failed: {e}")


def get_recent_alerts(limit: int = 50, alert_type: Optional[str] = None) -> list[dict]:
    """获取最近预警记录。"""
    try:
        db = SessionLocal()
        try:
            q = db.query(Alert).filter(Alert.is_archived == False)
            if alert_type:
                q = q.filter(Alert.type == alert_type)
            rows = q.order_by(Alert.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "type": r.type,
                    "severity": r.severity,
                    "code": r.code,
                    "title": r.title,
                    "message": r.message,
                    "isRead": r.is_read,
                    "createdAt": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        print(f"[Alert] Query failed: {e}")
        return []


def mark_alert_read(alert_id: int) -> bool:
    """标记预警为已读。"""
    try:
        db = SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if alert:
                alert.is_read = True
                db.commit()
                return True
        finally:
            db.close()
    except Exception:
        pass
    return False


def mark_all_read() -> int:
    """全部标记已读。"""
    try:
        db = SessionLocal()
        try:
            count = db.query(Alert).filter(Alert.is_read == False).update({"is_read": True})
            db.commit()
            return count
        finally:
            db.close()
    except Exception:
        return 0
