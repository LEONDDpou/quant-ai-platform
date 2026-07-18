"""模拟盘交易系统 — 风险控制服务（M5 核心）。

职责：
1. 风险参数配置（按账户维度，开启/阈值 CRUD）；
2. 前置风控（pre-trade）：下单前校验单票集中度 / 总仓位 / 单笔金额 / 单日亏损，
   任一越限即拦截并生成风险事件；
3. 实时风险指标计算（集中度 / 总仓位 / 当日亏损 / 个股止损 / 综合状态）；
4. 风险事件记录与去重扫描（集中度突破 / 单日亏损触限 / 个股止损破线）。

设计约束：与订单 / 持仓服务解耦，仅在自身 Session 内读取，不在本服务内改动资金或持仓。
"""
from datetime import datetime
from typing import Optional

from app.paper.domain_models import PaperRiskConfig
from app.paper.repositories.account_repo import AccountRepository
from app.paper.services.position_service import PositionService
from app.paper.services.risk_repo import (
    RiskConfigRepository,
    RiskEventRepository,
    RiskRuleRepository,
)
from app.paper.services.market_provider import market_provider
from app.paper.schemas import (
    RiskConfigRequest,
    RiskConfigResponse,
    RiskRuleRequest,
    RiskRuleResponse,
    RiskReportResponse,
)
from app.paper.errors import PaperError

# 平台默认风险参数（未配置时使用）
DEFAULT_CONFIG = {
    "enabled": True,
    "maxPositionRatio": 0.5,        # 单票最大仓位 50%
    "maxTotalPositionRatio": 0.9,   # 总仓位上限 90%
    "maxSingleAmount": 500000.0,    # 单笔最大委托 50 万
    "maxDailyLoss": 50000.0,        # 单日最大亏损 5 万
    "stopLossRatio": 0.20,          # 个股止损线 20%
    "allowShort": False,            # 不允许卖空
}

# 状态严重度排序（用于综合判定）
_STATUS_RANK = {"ok": 0, "warn": 1, "breach": 2}


class RiskService:
    """风险控制服务（M5）。"""

    def __init__(self):
        self.config_repo = RiskConfigRepository()
        self.event_repo = RiskEventRepository()
        self.rule_repo = RiskRuleRepository()
        self.position_svc = PositionService()

    # ——————————————————————— 配置 ———————————————————————
    def get_config(self, account_id: int) -> dict:
        """返回账户风险配置（无记录则取平台默认）。"""
        row = self.config_repo.get_by_account(account_id)
        if row is None:
            return dict(DEFAULT_CONFIG)
        return {
            "enabled": row.enabled,
            "maxPositionRatio": row.max_position_ratio,
            "maxTotalPositionRatio": row.max_total_position_ratio,
            "maxSingleAmount": row.max_single_amount,
            "maxDailyLoss": row.max_daily_loss,
            "stopLossRatio": row.stop_loss_ratio,
            "allowShort": row.allow_short,
        }

    def upsert_config(self, account_id: int, req: RiskConfigRequest) -> RiskConfigResponse:
        """新增或更新账户风险配置。"""
        row = self.config_repo.upsert(
            account_id,
            enabled=req.enabled,
            max_position_ratio=req.maxPositionRatio,
            max_total_position_ratio=req.maxTotalPositionRatio,
            max_single_amount=req.maxSingleAmount,
            max_daily_loss=req.maxDailyLoss,
            stop_loss_ratio=req.stopLossRatio,
            allow_short=req.allowShort,
        )
        return RiskConfigResponse(
            accountId=account_id,
            enabled=row.enabled,
            maxPositionRatio=row.max_position_ratio,
            maxTotalPositionRatio=row.max_total_position_ratio,
            maxSingleAmount=row.max_single_amount,
            maxDailyLoss=row.max_daily_loss,
            stopLossRatio=row.stop_loss_ratio,
            allowShort=row.allow_short,
        )

    # ——————————————————————— 实时资产口径 ———————————————————————
    def _live_total_assets(self, account_id: int) -> float:
        """实时总资产 = 现金 + 实时持仓市值（替代陈旧的 acct.total_assets）。

        acct.total_assets 仅在开户/改资金时更新，盘中日浮盈亏不会回写，
        用于风控比例会与 compute_account_metrics 口径不一致。改为实时派生。
        """
        acct = AccountRepository().get_account(account_id)
        if not acct:
            return 0.0
        positions = self.position_svc.list_positions(account_id)
        mv = sum(p.marketValue for p in positions)
        return (acct.cash or 0.0) + mv

    def _live_position_value(self, account_id: int) -> float:
        """实时持仓市值（替代陈旧的 acct.position_value）。"""
        positions = self.position_svc.list_positions(account_id)
        return sum(p.marketValue for p in positions)

    # ——————————————————————— 前置风控 ———————————————————————
    def evaluate_pre_trade(self, account_id: int, code: str, direction: str,
                           order_type: str, price: float, quantity: int):
        """下单前置风控校验。返回 (ok, violations)。

        仅对买入方向做强约束（集中度 / 总仓位 / 单笔金额 / 单日亏损）；
        卖出降低风险敞口，放行（卖空由 M3 持仓校验拦截，配置 allowShort 仅作记录）。

        A 股特有规则（#P0）：
        - 涨跌停价拦截（买入>=涨停价 / 卖出<=跌停价）
        - 自成交检测（同账户同标的既有挂买单又挂卖单）
        - ST 5% 涨跌停限制
        """
        cfg = self.get_config(account_id)
        if not cfg["enabled"]:
            return True, []
        violations: list[str] = []

        # ———— A 股特有规则（#P0） ————
        from app.paper.trading_session import get_price_limit_pct, is_st_stock

        try:
            q = market_provider.quote(code)
            # quote 返回字段为 prevClose（昨收），涨停/跌停价基于昨收计算
            prev_close = (q or {}).get("prevClose") or (q or {}).get("close") or 0
            if q and prev_close > 0:
                close = float(prev_close)
                name = str(q.get("name", ""))
                limit_pct = 0.05 if is_st_stock(name) else get_price_limit_pct(code)
                upper = round(close * (1 + limit_pct), 2)
                lower = round(close * (1 - limit_pct), 2)
                if direction == "buy" and price > 0 and price >= upper:
                    violations.append(f"买入价 {price} 触及涨停价 {upper}（{name} {limit_pct*100:.0f}%限制）")
                if direction == "sell" and price > 0 and price <= lower:
                    violations.append(f"卖出价 {price} 触及跌停价 {lower}（{name} {limit_pct*100:.0f}%限制）")
        except Exception:
            pass  # 行情获取失败不阻塞下单

        # 自成交检测：同一账户对同一标的同时有买和卖挂单
        try:
            from app.paper.services.order_service import OrderService
            orders = OrderService().list_orders(account_id, status="pending")
            for o in orders:
                if o.code == code and o.direction != direction:
                    violations.append(f"自成交风险：账户已有 {o.direction} 方向挂单 {code}")
                    break
        except Exception:
            pass

        # ———— 原有规则 ————
        if direction != "buy":
            return (len(violations) == 0), violations

        # 单笔金额上限
        if order_type in ("limit", "market", "ai") and price > 0 and cfg["maxSingleAmount"] > 0:
            amt = price * quantity
            if amt > cfg["maxSingleAmount"] + 1e-6:
                violations.append(
                    f"单笔委托金额 {amt:,.0f} 元超过上限 {cfg['maxSingleAmount']:,.0f} 元")

        acct = AccountRepository().get_account(account_id)
        total_assets = self._live_total_assets(account_id)
        if total_assets <= 0:
            return (len(violations) == 0), violations

        positions = self.position_svc.list_positions(account_id)  # list[PositionResponse]
        cur = next((p for p in positions if p.code == code), None)
        cur_mv = cur.marketValue if cur else 0.0
        cur_shares = cur.shares if cur else 0

        # 保守成交价：限价/AI 用委托价；市价用实时价
        est_price = price
        if order_type == "market":
            est_price = float(market_provider.quote(code).get("price") or 0.0)
        if est_price <= 0:
            return (len(violations) == 0), violations

        new_shares = cur_shares + quantity
        new_mv = new_shares * est_price

        # 单票集中度
        if cfg["maxPositionRatio"] > 0:
            ratio = new_mv / total_assets
            if ratio > cfg["maxPositionRatio"] + 1e-9:
                violations.append(
                    f"下单后「{code}」仓位占比 {ratio * 100:.1f}% 超过单票上限 "
                    f"{cfg['maxPositionRatio'] * 100:.1f}%")

        # 总仓位
        if cfg["maxTotalPositionRatio"] > 0:
            total_mv = sum(p.marketValue for p in positions) - cur_mv + new_mv
            tratio = total_mv / total_assets
            if tratio > cfg["maxTotalPositionRatio"] + 1e-9:
                violations.append(
                    f"下单后总仓位 {tratio * 100:.1f}% 超过上限 "
                    f"{cfg['maxTotalPositionRatio'] * 100:.1f}%")

        # 单日亏损触限：禁止新建多头
        if cfg["maxDailyLoss"] > 0:
            summary = self.position_svc.get_summary(account_id)
            today_loss = max(0.0, -summary["todayPnl"])
            if today_loss >= cfg["maxDailyLoss"] - 1e-6:
                violations.append(
                    f"今日亏损已达 {today_loss:,.0f} 元，触及单日亏损上限 "
                    f"{cfg['maxDailyLoss']:,.0f} 元，禁止新建多头")

        return (len(violations) == 0), violations

    # ——————————————————————— 实时指标 ———————————————————————
    def metrics(self, account_id: int) -> dict:
        """计算账户实时风险指标（供前端面板 / 定时扫描使用）。"""
        cfg = self.get_config(account_id)
        acct = AccountRepository().get_account(account_id)
        total_assets = self._live_total_assets(account_id)
        position_value = self._live_position_value(account_id)

        summary = self.position_svc.get_summary(account_id)
        positions = self.position_svc.list_positions(account_id)

        total_mv = position_value
        total_position_ratio = (total_mv / total_assets) if total_assets else 0.0
        max_pos = (max((p.marketValue / total_assets * 100.0) for p in positions)
                   if total_assets and positions else 0.0)
        today_pnl = summary["todayPnl"]
        daily_loss = max(0.0, -today_pnl)
        daily_loss_ratio = (daily_loss / cfg["maxDailyLoss"]) if cfg["maxDailyLoss"] else 0.0

        breaches: list[str] = []
        single_status = "ok"
        total_status = "ok"

        # 单票集中度
        if cfg["maxPositionRatio"] > 0:
            if max_pos > cfg["maxPositionRatio"] + 1e-9:
                single_status = "breach"
                breaches.append(
                    f"单票持仓 {max_pos * 100:.1f}% 超过上限 {cfg['maxPositionRatio'] * 100:.1f}%")
            elif max_pos > cfg["maxPositionRatio"] * 0.8:
                single_status = "warn"
        # 总仓位
        if cfg["maxTotalPositionRatio"] > 0:
            if total_position_ratio > cfg["maxTotalPositionRatio"] + 1e-9:
                total_status = "breach"
                breaches.append(
                    f"总仓位 {total_position_ratio * 100:.1f}% 超过上限 "
                    f"{cfg['maxTotalPositionRatio'] * 100:.1f}%")
            elif total_position_ratio > cfg["maxTotalPositionRatio"] * 0.8:
                total_status = "warn"

        concentration_status = "breach" if ("breach" in (single_status, total_status)) else \
            ("warn" if ("warn" in (single_status, total_status)) else "ok")

        # 单日亏损
        daily_loss_status = "ok"
        if cfg["maxDailyLoss"] > 0:
            if daily_loss_ratio >= 1.0 - 1e-9:
                daily_loss_status = "breach"
                breaches.append(
                    f"今日亏损 {daily_loss:,.0f} 元，已达单日上限 {cfg['maxDailyLoss']:,.0f} 元")
            elif daily_loss_ratio >= 0.8:
                daily_loss_status = "warn"

        # 个股止损
        stop_loss_status = "ok"
        if cfg["stopLossRatio"] > 0 and positions:
            for p in positions:
                if p.shares > 0 and p.pnlPct <= -cfg["stopLossRatio"] * 100:
                    stop_loss_status = "breach"
                    breaches.append(
                        f"「{p.code} {p.name}」浮亏 {p.pnlPct:.1f}% 触及止损线 "
                        f"{-cfg['stopLossRatio'] * 100:.0f}%")
            if stop_loss_status == "ok":
                # 接近止损线（≥80%）标 warn
                if any(p.shares > 0 and p.pnlPct <= -cfg["stopLossRatio"] * 80
                       for p in positions):
                    stop_loss_status = "warn"

        overall = "ok"
        for s in (concentration_status, daily_loss_status, stop_loss_status):
            if _STATUS_RANK[s] > _STATUS_RANK[overall]:
                overall = s

        return {
            "accountId": account_id,
            "totalAssets": round(total_assets, 2),
            "positionValue": round(position_value, 2),
            "totalPositionRatio": round(total_position_ratio, 4),
            "maxPositionRatio": round(max_pos, 4),
            "todayPnl": round(today_pnl, 2),
            "dailyLoss": round(daily_loss, 2),
            "dailyLossRatio": round(daily_loss_ratio, 4),
            "concentrationStatus": concentration_status,
            "stopLossStatus": stop_loss_status,
            "dailyLossStatus": daily_loss_status,
            "overallStatus": overall,
            "breaches": breaches,
            "configSnapshot": cfg,
        }

    # ——————————————————————— 事件 ———————————————————————
    def list_events(self, account_id: int, limit: int = 100, acked: Optional[bool] = None):
        return self.event_repo.list_events(account_id, limit=limit, acked=acked)

    def record_event(self, account_id: int, code: str, event_type: str, level: str,
                     message: str, detail=None) -> int:
        """记录一条风险事件（不去重，供下单拦截即时落库）。返回新增条数。"""
        self.event_repo.add(account_id, code, event_type, level, message, detail or {})
        return 1

    def _record_once(self, account_id: int, code: str, event_type: str, level: str,
                     message: str, detail) -> int:
        """去重记录：近期（24h）同类型 + 同标的未处理事件已存在则跳过。"""
        if self.event_repo.recent_unacked(account_id, event_type, code):
            return 0
        self.event_repo.add(account_id, code, event_type, level, message, detail or {})
        return 1

    def scan_breaches(self, account_id: int) -> int:
        """扫描当前账户风险突破并落库（去重），返回新增事件数。"""
        m = self.metrics(account_id)
        recorded = 0
        if m["concentrationStatus"] == "breach":
            msg = "；".join(b for b in m["breaches"] if ("仓位" in b or "总仓位" in b)) \
                or "持仓集中度突破上限"
            recorded += self._record_once(account_id, "", "CONCENTRATION_BREACH", "high",
                                          msg, {"metrics": m})
        if m["dailyLossStatus"] == "breach":
            recorded += self._record_once(
                account_id, "", "DAILY_LOSS_BREACH", "critical",
                f"今日亏损 {m['dailyLoss']:,.0f} 元，已达单日上限",
                {"dailyLoss": m["dailyLoss"], "limit": m["configSnapshot"]["maxDailyLoss"]})
        if m["stopLossStatus"] == "breach":
            cfg = self.get_config(account_id)
            for p in self.position_svc.list_positions(account_id):
                if p.shares > 0 and p.pnlPct <= -cfg["stopLossRatio"] * 100:
                    recorded += self._record_once(
                        account_id, p.code, "STOP_LOSS_BREACH", "high",
                        f"「{p.code} {p.name}」浮亏 {p.pnlPct:.1f}% 触及止损线",
                        {"pnlPct": p.pnlPct, "stopLossRatio": cfg["stopLossRatio"]})
        return recorded

    # ——————————————————————— 智能风控中心：规则引擎 ———————————————————————
    def list_rules(self, account_id: int):
        """列出账户生效规则（账户规则 + 全局规则）。"""
        return self.rule_repo.list_rules(account_id)

    def create_rule(self, account_id: int, req: RiskRuleRequest) -> RiskRuleResponse:
        """为账户新增一条风控规则（scope 默认 account）。"""
        rule = self.rule_repo.create(account_id, req)
        return self._rule_to_resp(rule)

    def update_rule(self, account_id: int, rule_id: int, req: RiskRuleRequest) -> RiskRuleResponse:
        """更新账户的一条风控规则。"""
        rule = self.rule_repo.update(rule_id, account_id, req)
        return self._rule_to_resp(rule)

    def delete_rule(self, rule_id: int) -> bool:
        """删除一条规则。"""
        return self.rule_repo.delete(rule_id)

    def _rule_to_resp(self, rule) -> RiskRuleResponse:
        return RiskRuleResponse(
            id=rule.id, accountId=rule.account_id, name=rule.name,
            ruleType=rule.rule_type, threshold=rule.threshold, scope=rule.scope,
            enabled=rule.enabled, severity=rule.severity, detail=rule.detail or {},
            createdAt=rule.created_at.isoformat() if rule.created_at else "",
            updatedAt=rule.updated_at.isoformat() if rule.updated_at else "",
        )

    # ——————————————————————— 事件已读工作流 ———————————————————————
    def ack_event(self, event_id: int, acked: bool = True) -> bool:
        """标记单条风险事件已读/未读。"""
        self.event_repo.ack(event_id, acked)
        return True

    def ack_all(self, account_id: int) -> int:
        """标记账户全部未读风险事件为已读，返回处理条数。"""
        events = self.event_repo.list_events(account_id, acked=False)
        for ev in events:
            self.event_repo.ack(ev.id, True)
        return len(events)

    # ——————————————————————— 规则评估（供自动监控循环调用） ———————————————————————
    def evaluate_rules(self, account_id: int) -> int:
        """评估账户全部启用规则，命中则去重落库风险事件，返回新增事件数。

        支持类型：黑名单命中 / 行业集中度 / 最大回撤 / 杠杆(仓位) / 隔夜占比 / 自定义。
        """
        rules = self.list_rules(account_id)
        enabled = [r for r in rules if r.enabled]
        if not enabled:
            return 0
        positions = self.position_svc.list_positions(account_id)
        summary = self.position_svc.get_summary(account_id)
        acct = AccountRepository().get_account(account_id)
        total_assets = (acct.total_assets or 0.0) if acct else 0.0
        recorded = 0
        for rule in enabled:
            triggered, message = self._eval_one(rule, account_id, positions, summary, total_assets, acct)
            if triggered:
                recorded += self._record_once(
                    account_id, "", f"RULE_{rule.rule_type}", rule.severity,
                    f"[规则 {rule.name}] {message}",
                    {"ruleId": rule.id, "ruleType": rule.rule_type, "threshold": rule.threshold},
                )
        return recorded

    def _eval_one(self, rule, account_id, positions, summary, total_assets, acct):
        """评估单条规则，返回 (是否触发, 说明)。纯确定性逻辑，不调用外部服务。"""
        rt = rule.rule_type
        if rt == "BLACKLIST":
            codes = [str(c) for c in (rule.detail or {}).get("codes", [])]
            hit = [p.code for p in positions if p.code in codes]
            if hit:
                return True, f"持仓命中黑名单：{', '.join(hit)}"
            return False, ""
        if rt == "SECTOR_CONCENTRATION":
            max_ratio = rule.threshold  # 百分比（如 40 表示 40%）
            for d in summary.get("industryDistribution", []):
                if d.get("ratio", 0.0) > max_ratio + 1e-9:
                    return True, f"行业「{d.get('industry')}」占比 {d.get('ratio'):.1f}% 超过上限 {max_ratio:.1f}%"
            return False, ""
        if rt == "MAX_DRAWDOWN":
            max_dd = rule.threshold  # 百分比
            dd = (acct.max_drawdown or 0.0) if acct else 0.0
            if max_dd > 0 and dd > max_dd + 1e-9:
                return True, f"账户最大回撤 {dd:.2f}% 已超过阈值 {max_dd:.2f}%"
            return False, ""
        if rt in ("LEVERAGE", "OVERNIGHT_LIMIT"):
            max_ratio = rule.threshold  # 百分比（持仓占比上限）
            pr = (summary.get("totalMarketValue", 0.0) / total_assets * 100.0) if total_assets else 0.0
            if max_ratio > 0 and pr > max_ratio + 1e-9:
                return True, f"持仓占比 {pr:.1f}% 超过上限 {max_ratio:.1f}%"
            return False, ""
        if rt == "CUSTOM":
            # 自定义规则：detail.condition="always" 时强制触发，默认不触发（避免误报）
            cond = (rule.detail or {}).get("condition", "never")
            if cond == "always":
                return True, rule.detail.get("message", "自定义规则触发")
            return False, ""
        return False, ""

    # ——————————————————————— 风险报告（确定性算法，不依赖 LLM） ———————————————————————
    def build_report(self, account_id: int) -> RiskReportResponse:
        """生成结构化风险报告（确定性算法），供前端面板与 AI 复盘订阅使用。"""
        m = self.metrics(account_id)
        rules = self.list_rules(account_id)
        active_rules = [r for r in rules if r.enabled]

        # 评估规则触发（与自动监控一致）
        positions = self.position_svc.list_positions(account_id)
        summary = self.position_svc.get_summary(account_id)
        acct = AccountRepository().get_account(account_id)
        total_assets = (acct.total_assets or 0.0) if acct else 0.0
        triggered_rules: list[dict] = []
        for rule in active_rules:
            triggered, message = self._eval_one(rule, account_id, positions, summary, total_assets, acct)
            if triggered:
                triggered_rules.append({
                    "ruleId": rule.id, "name": rule.name, "ruleType": rule.rule_type,
                    "severity": rule.severity, "message": message,
                })

        # 风险评分：基础分 + 触发严重度 + 指标综合状态 + 未读事件
        sev_weight = {"warn": 15, "high": 30, "critical": 50}
        score = 0
        for t in triggered_rules:
            score += sev_weight.get(t["severity"], 15)
        score += {"ok": 0, "warn": 10, "breach": 30}.get(m["overallStatus"], 0)
        unacked = self.event_repo.list_events(account_id, acked=False)
        score += min(len(unacked), 5) * 4
        score = min(100, score)

        status = m["overallStatus"]
        if status == "ok" and triggered_rules:
            status = "warn"

        # 处置建议（确定性）
        suggestions: list[str] = []
        for b in m["breaches"]:
            suggestions.append(f"针对「{b}」及时减仓或对冲")
        for t in triggered_rules:
            suggestions.append(f"规则「{t['name']}」已触发：{t['message']}")
        if not suggestions:
            suggestions.append("当前风险敞口在阈值内，保持现有仓位管理节奏")

        summary_text = (
            f"综合风险状态：{status}；风险评分 {score}/100；"
            f"启用规则 {len(active_rules)} 条，触发 {len(triggered_rules)} 条；"
            f"未处理风险事件 {len(unacked)} 条。"
        )
        return RiskReportResponse(
            accountId=account_id,
            generatedAt=datetime.utcnow().isoformat(),
            overallStatus=status,
            score=round(score, 1),
            summary=summary_text,
            metrics=m,
            activeRules=len(active_rules),
            triggeredRules=triggered_rules,
            topBreaches=m["breaches"],
            suggestions=suggestions,
        )
