"""预警 API — 预警列表、规则配置、已读管理。"""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import alert_engine as ae

router = APIRouter()


class RuleUpdate(BaseModel):
    name: str
    type: str
    condition: dict
    enabled: bool = True
    cooldown_min: int = 5


@router.get("")
def get_alerts(
    limit: int = Query(50, ge=5, le=200),
    type: str = Query(None, description="按类型筛选: technical/capital/event/risk"),
):
    """获取预警列表（最近N条，可筛选类型）。"""
    alerts = ae.get_recent_alerts(limit=limit, alert_type=type)
    return {
        "alerts": alerts,
        "total": len(alerts),
        "types": {
            "info": sum(1 for a in alerts if a["severity"] == "info"),
            "warning": sum(1 for a in alerts if a["severity"] == "warning"),
            "critical": sum(1 for a in alerts if a["severity"] == "critical"),
        },
    }


@router.get("/rules")
def get_rules():
    """获取当前预警规则配置。"""
    return ae.get_alert_rules()


@router.put("/rules")
def update_rule(rule: RuleUpdate):
    """更新预警规则。"""
    try:
        from app.db.database import SessionLocal
        from app.db.models import AlertRule
        db = SessionLocal()
        try:
            existing = db.query(AlertRule).filter(
                AlertRule.name == rule.name, AlertRule.type == rule.type
            ).first()
            if existing:
                existing.condition = rule.condition
                existing.enabled = rule.enabled
                existing.cooldown_min = rule.cooldown_min
            else:
                db.add(AlertRule(
                    name=rule.name,
                    type=rule.type,
                    condition=rule.condition,
                    enabled=rule.enabled,
                    cooldown_min=rule.cooldown_min,
                ))
            db.commit()
            return {"status": "ok"}
        finally:
            db.close()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/mark-read/{alert_id}")
def mark_read(alert_id: int):
    """标记单条预警为已读。"""
    ok = ae.mark_alert_read(alert_id)
    return {"status": "ok" if ok else "not_found"}


@router.post("/mark-all-read")
def mark_all_read():
    """全部标记为已读。"""
    count = ae.mark_all_read()
    return {"status": "ok", "marked": count}
