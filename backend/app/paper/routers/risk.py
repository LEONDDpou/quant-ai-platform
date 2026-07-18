"""模拟盘交易系统 — 风险控制路由（M5）。

挂载前缀：/api/paper/risk
端点：
    GET  /{account_id}/config    风险参数配置
    PUT  /{account_id}/config    新增/更新风险参数
    GET  /{account_id}/metrics   实时风险指标
    GET  /{account_id}/events    风险事件列表
    POST /{account_id}/scan      扫描并落库当前风险突破
"""
from fastapi import APIRouter, HTTPException, Query

from app.paper.schemas import (
    RiskConfigRequest,
    RiskConfigResponse,
    RiskMetrics,
    RiskEventResponse,
    RiskRuleRequest,
    RiskRuleResponse,
    RiskReportResponse,
)
from app.paper.services.risk_service import RiskService
from app.paper.errors import PaperError

router = APIRouter(tags=["PaperRisk"])
_risk = RiskService()


@router.get("/{account_id}/config", response_model=RiskConfigResponse)
def get_risk_config(account_id: int):
    """获取账户风险参数配置（无记录返回平台默认）。"""
    try:
        cfg = _risk.get_config(account_id)
        return RiskConfigResponse(accountId=account_id, **cfg)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.put("/{account_id}/config", response_model=RiskConfigResponse)
def upsert_risk_config(account_id: int, req: RiskConfigRequest):
    """新增或更新账户风险参数配置。"""
    try:
        return _risk.upsert_config(account_id, req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/metrics", response_model=RiskMetrics)
def risk_metrics(account_id: int):
    """实时风险指标（集中度 / 总仓位 / 当日亏损 / 个股止损 / 综合状态）。"""
    try:
        return _risk.metrics(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/{account_id}/events", response_model=list[RiskEventResponse])
def risk_events(account_id: int, limit: int = Query(100, ge=1, le=500),
               acked: bool = Query(None)):
    """风险事件列表（按时间倒序）。"""
    try:
        events = _risk.list_events(account_id, limit=limit, acked=acked)
        return [
            RiskEventResponse(
                id=e.id, accountId=e.account_id, code=e.code, eventType=e.event_type,
                level=e.level, message=e.message, detail=e.detail or {},
                acked=e.acked, createdAt=e.created_at.isoformat() if e.created_at else "",
            )
            for e in events
        ]
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/scan")
def scan_risk(account_id: int):
    """扫描当前账户风险突破并去重落库，返回新增事件数。"""
    try:
        return {"recorded": _risk.scan_breaches(account_id)}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


# ====================== 智能风控中心：规则引擎 ======================
@router.get("/{account_id}/rules", response_model=list[RiskRuleResponse])
def list_risk_rules(account_id: int):
    """列出账户生效规则（账户规则 + 全局规则）。"""
    try:
        return [_risk._rule_to_resp(r) for r in _risk.list_rules(account_id)]
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/rules", response_model=RiskRuleResponse)
def create_risk_rule(account_id: int, req: RiskRuleRequest):
    """为账户新增一条风控规则。"""
    try:
        return _risk.create_rule(account_id, req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.put("/{account_id}/rules/{rule_id}", response_model=RiskRuleResponse)
def update_risk_rule(account_id: int, rule_id: int, req: RiskRuleRequest):
    """更新账户的一条风控规则。"""
    try:
        return _risk.update_rule(account_id, rule_id, req)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/{account_id}/rules/{rule_id}")
def delete_risk_rule(account_id: int, rule_id: int):
    """删除一条风控规则。"""
    try:
        return {"deleted": _risk.delete_rule(rule_id)}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


# ====================== 智能风控中心：事件已读工作流 ======================
@router.post("/{account_id}/events/{event_id}/ack")
def ack_risk_event(account_id: int, event_id: int):
    """标记单条风险事件为已读。"""
    try:
        _risk.ack_event(event_id, True)
        return {"acked": True}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/{account_id}/events/ack-all")
def ack_all_risk_events(account_id: int):
    """标记账户全部未读风险事件为已读。"""
    try:
        return {"acked": _risk.ack_all(account_id)}
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)


# ====================== 智能风控中心：风险报告 ======================
@router.get("/{account_id}/report", response_model=RiskReportResponse)
def risk_report(account_id: int):
    """生成确定性风险报告（指标 + 规则触发 + 处置建议）。"""
    try:
        return _risk.build_report(account_id)
    except PaperError as e:
        raise HTTPException(status_code=400, detail=e.message)
