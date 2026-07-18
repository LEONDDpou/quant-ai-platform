"""模拟盘交易系统 — 风险数据仓储（M5 + 智能风控中心增强）。

遵循项目统一的 Repository 模式（与 order_repo / position_repo 一致），
所有方法在独立 Session 内完成，避免长事务与连接泄漏。
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_

from app.paper.domain_models import PaperRiskConfig, PaperRiskEvent, PaperRiskRule
from app.paper.repositories.base import BaseRepository
from app.paper.schemas import RiskRuleRequest


class RiskConfigRepository(BaseRepository):
    """风险参数配置仓储。"""

    model = PaperRiskConfig

    def get_by_account(self, account_id: int):
        with self._session() as db:
            return (
                db.query(PaperRiskConfig)
                .filter(PaperRiskConfig.account_id == account_id)
                .first()
            )

    def upsert(self, account_id: int, **fields) -> PaperRiskConfig:
        with self._session() as db:
            cfg = (
                db.query(PaperRiskConfig)
                .filter(PaperRiskConfig.account_id == account_id)
                .first()
            )
            if cfg is None:
                cfg = PaperRiskConfig(account_id=account_id)
                db.add(cfg)
            for k, v in fields.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
            cfg.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(cfg)
            return cfg


class RiskEventRepository(BaseRepository):
    """风险事件仓储。"""

    model = PaperRiskEvent

    def list_events(self, account_id: int, limit: int = 100, acked=None):
        with self._session() as db:
            q = db.query(PaperRiskEvent).filter(PaperRiskEvent.account_id == account_id)
            if acked is not None:
                q = q.filter(PaperRiskEvent.acked == acked)
            return q.order_by(PaperRiskEvent.created_at.desc()).limit(limit).all()

    def recent_unacked(self, account_id: int, event_type: str, code: str, within_minutes: int = 1440):
        """查找近期（默认 24h 内）同类型 + 同标的、尚未处理的风险事件，用于去重。"""
        since = datetime.utcnow() - timedelta(minutes=within_minutes)
        with self._session() as db:
            return (
                db.query(PaperRiskEvent)
                .filter(
                    and_(
                        PaperRiskEvent.account_id == account_id,
                        PaperRiskEvent.event_type == event_type,
                        PaperRiskEvent.code == code,
                        PaperRiskEvent.acked == False,  # noqa: E712
                        PaperRiskEvent.created_at >= since,
                    )
                )
                .first()
            )

    def add(self, account_id: int, code: str, event_type: str, level: str,
            message: str, detail=None) -> PaperRiskEvent:
        with self._session() as db:
            ev = PaperRiskEvent(
                account_id=account_id, code=code, event_type=event_type,
                level=level, message=message, detail=detail or {},
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)
            return ev

    def ack(self, event_id: int, acked: bool = True) -> PaperRiskEvent:
        """标记风险事件已读/未读。"""
        with self._session() as db:
            ev = db.get(PaperRiskEvent, event_id)
            if not ev:
                raise PaperError(f"风险事件不存在: {event_id}")
            ev.acked = acked
            db.commit()
            db.refresh(ev)
            return ev


class RiskRuleRepository(BaseRepository):
    """智能风控中心 — 可配置规则引擎仓储。"""

    model = PaperRiskRule

    def list_rules(self, account_id: Optional[int] = None):
        """列出规则：传入 account_id 时返回「该账户规则 + 全局规则」；否则仅全局规则。"""
        with self._session() as db:
            q = db.query(PaperRiskRule)
            if account_id is not None:
                q = q.filter(
                    (PaperRiskRule.account_id == account_id)
                    | (PaperRiskRule.account_id.is_(None))
                )
            else:
                q = q.filter(PaperRiskRule.account_id.is_(None))
            return q.order_by(PaperRiskRule.created_at.desc()).all()

    def create(self, account_id: Optional[int], req: RiskRuleRequest) -> PaperRiskRule:
        """按请求创建一条规则（scope/account_id 由调用方决定）。"""
        rule = PaperRiskRule(
            account_id=account_id,
            name=req.name,
            rule_type=req.ruleType,
            threshold=req.threshold,
            scope=req.scope,
            enabled=req.enabled,
            severity=req.severity,
            detail=req.detail or {},
        )
        with self._session() as db:
            db.add(rule)
            db.commit()
            db.refresh(rule)
            return rule

    def update(self, rule_id: int, account_id: Optional[int], req: RiskRuleRequest) -> PaperRiskRule:
        """更新规则；账户规则不可越权修改他人/全局规则。"""
        with self._session() as db:
            rule = db.get(PaperRiskRule, rule_id)
            if rule is None:
                raise PaperError(f"规则不存在: {rule_id}")
            if account_id is not None and rule.account_id is not None \
                    and rule.account_id != account_id:
                raise PaperError(f"无权修改其他账户的规则: {rule_id}")
            rule.name = req.name
            rule.rule_type = req.ruleType
            rule.threshold = req.threshold
            rule.scope = req.scope
            rule.enabled = req.enabled
            rule.severity = req.severity
            rule.detail = req.detail or {}
            rule.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(rule)
            return rule
