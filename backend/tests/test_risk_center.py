"""模拟盘交易系统 — 智能风控中心单元测试（无服务依赖，内存 SQLite）。

覆盖：规则引擎 CRUD / 事件已读工作流 / 规则评估（黑名单命中）/ 确定性风险报告结构。
运行：cd backend && python -m unittest tests.test_risk_center -v
"""
import os
import tempfile
import unittest

# 必须在导入 app 任何模块前固定数据库连接为临时文件 SQLite，避免污染生产库
_TMP_DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

from app.db.database import init_db, SessionLocal  # noqa: E402
from app.paper.domain_models import (  # noqa: E402
    PaperAccount,
    PaperPosition,
    PaperRiskEvent,
)
from app.paper.services.risk_service import RiskService  # noqa: E402
from app.paper.services.risk_repo import RiskEventRepository  # noqa: E402
from app.paper.schemas import RiskRuleRequest  # noqa: E402


class TestRiskCenter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with SessionLocal() as db:
            acct = PaperAccount(
                name="风控中心测试账户",
                initial_capital=1_000_000.0,
                cash=500_000.0,
                total_assets=1_000_000.0,
                position_value=500_000.0,
                max_drawdown=10.0,
            )
            db.add(acct)
            db.commit()
            db.refresh(acct)
            cls.account_id = acct.id
            # 一个白酒持仓：市值 40 万，占总资产 40%
            pos = PaperPosition(
                account_id=acct.id, code="600519", name="贵州茅台",
                industry="白酒", shares=100, cost_price=4000.0,
                current_price=4000.0, market_value=400_000.0,
                pnl_pct=-5.0, position_ratio=40.0,
            )
            db.add(pos)
            db.commit()

    # ———————————————————— 规则引擎 CRUD ————————————————————
    def test_rule_crud(self):
        svc = RiskService()
        rule = svc.create_rule(
            self.account_id,
            RiskRuleRequest(name="白酒限仓", ruleType="SECTOR_CONCENTRATION",
                            threshold=30.0, severity="high"),
        )
        self.assertIsNotNone(rule.id)
        self.assertEqual(rule.accountId, self.account_id)

        rules = svc.list_rules(self.account_id)
        self.assertTrue(any(r.id == rule.id for r in rules))

        updated = svc.update_rule(
            self.account_id, rule.id,
            RiskRuleRequest(name="白酒限仓2", ruleType="SECTOR_CONCENTRATION",
                            threshold=25.0, severity="critical"),
        )
        self.assertEqual(updated.threshold, 25.0)
        self.assertEqual(updated.severity, "critical")

        self.assertTrue(svc.delete_rule(rule.id))
        self.assertFalse(any(r.id == rule.id for r in svc.list_rules(self.account_id)))

    # ———————————————————— 事件已读工作流 ————————————————————
    def test_ack_workflow(self):
        ev_repo = RiskEventRepository()
        ev = ev_repo.add(self.account_id, "600519", "TEST_EVENT", "high", "测试事件", {})
        self.assertFalse(ev.acked)

        svc = RiskService()
        svc.ack_event(ev.id, True)
        with SessionLocal() as db:
            e = db.get(PaperRiskEvent, ev.id)
            self.assertTrue(e.acked)

        # 另造一条未读事件，验证 ack_all 计数
        ev2 = ev_repo.add(self.account_id, "000858", "TEST_EVENT2", "warn", "测试事件2", {})
        self.assertFalse(ev2.acked)
        n = svc.ack_all(self.account_id)
        self.assertGreaterEqual(n, 1)

    # ———————————————————— 规则评估：黑名单命中 ————————————————————
    def test_evaluate_rules_blacklist(self):
        svc = RiskService()
        svc.create_rule(
            self.account_id,
            RiskRuleRequest(name="黑名单", ruleType="BLACKLIST",
                            detail={"codes": ["600519"]}, severity="critical"),
        )
        recorded = svc.evaluate_rules(self.account_id)
        self.assertGreaterEqual(recorded, 1)

    # ———————————————————— 确定性风险报告结构 ————————————————————
    def test_build_report(self):
        svc = RiskService()
        svc.create_rule(
            self.account_id,
            RiskRuleRequest(name="行业限仓", ruleType="SECTOR_CONCENTRATION",
                            threshold=30.0, severity="high"),
        )
        rep = svc.build_report(self.account_id)
        self.assertEqual(rep.accountId, self.account_id)
        self.assertIn(rep.overallStatus, ("ok", "warn", "breach"))
        self.assertGreaterEqual(rep.score, 0)
        self.assertLessEqual(rep.score, 100)
        self.assertIsInstance(rep.triggeredRules, list)
        self.assertIsInstance(rep.suggestions, list)
        self.assertIsInstance(rep.topBreaches, list)
        self.assertGreater(rep.activeRules, 0)


if __name__ == "__main__":
    unittest.main()
