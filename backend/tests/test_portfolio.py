"""策略组合单元测试（确定性，零外网）。

用临时 SQLite 验证：
- CRUD（创建/获取/更新/删除）
- 策略分配格式
- run_portfolio（网络以桩隔离）
- rebalance（记录分配变更）
"""
import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import unittest
from unittest import mock


class TestPortfolio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.database import init_db, SessionLocal
        from app.paper.domain_models import PaperAccount
        init_db()
        db = SessionLocal()
        a = PaperAccount(name="组合单测", initial_capital=1_000_000.0)
        db.add(a)
        db.commit()
        cls.account_id = a.id
        db.close()

    def setUp(self):
        from app.paper.services.portfolio_service import PortfolioService
        self.svc = PortfolioService()

    def _req(self, name="测试组合", alloc=None, capital=1_000_000):
        from app.paper.schemas import PortfolioAllocation, PortfolioRequest
        return PortfolioRequest(
            accountId=self.account_id,
            name=name,
            description="组合描述",
            allocation=[PortfolioAllocation(strategyId=s, weight=w) for s, w in (alloc or {}).items()],
            totalCapital=capital,
            enabled=True,
        )

    def test_create_and_get(self):
        req = self._req("组合A", {"ai-001": 60, "ai-002": 40})
        resp = self.svc.create_portfolio(req)
        self.assertEqual(resp.name, "组合A")
        self.assertEqual(resp.strategyCount, 2)
        self.assertAlmostEqual(resp.totalCapital, 1_000_000)

        got = self.svc.get_portfolio(resp.id)
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "组合A")
        # 验证 allocation 内容
        alloc = {a.strategyId: a.weight for a in got.allocation}
        self.assertEqual(alloc["ai-001"], 60)

    def test_list(self):
        self.svc.create_portfolio(self._req("组合B"))
        self.svc.create_portfolio(self._req("组合C"))
        lst = self.svc.list_portfolios(self.account_id)
        names = [p.name for p in lst]
        self.assertIn("组合B", names)
        self.assertIn("组合C", names)

    def test_update(self):
        req = self._req("原名称", {"ai-001": 100})
        created = self.svc.create_portfolio(req)
        new_req = self._req("新名称", {"ai-001": 50, "ai-003": 50})
        updated = self.svc.update_portfolio(created.id, new_req)
        self.assertEqual(updated.name, "新名称")
        self.assertEqual(updated.strategyCount, 2)

    def test_delete(self):
        req = self._req("待删除")
        created = self.svc.create_portfolio(req)
        ok = self.svc.delete_portfolio(created.id)
        self.assertTrue(ok)
        self.assertIsNone(self.svc.get_portfolio(created.id))

    @mock.patch("app.paper.services.auto_trade_service.AutoTradeService")
    def test_run_portfolio(self, mock_at_cls):
        mock_at = mock_at_cls.return_value
        mock_at.run_once.return_value = None
        req = self._req("运行组合", {"ai-001": 60, "ai-002": 40})
        created = self.svc.create_portfolio(req)
        result = self.svc.run_portfolio(created.id)
        self.assertEqual(result["portfolioId"], created.id)
        self.assertEqual(mock_at.run_once.call_count, 2)

    def test_rebalance(self):
        req1 = self._req("再平衡前", {"ai-001": 100}, 1_000_000)
        created = self.svc.create_portfolio(req1)
        req2 = self._req("再平衡后", {"ai-001": 50, "ai-002": 50}, 2_000_000)
        rb = self.svc.rebalance(created.id, req2, reason="测试再平衡")
        self.assertEqual(rb.reason, "测试再平衡")
        self.assertEqual(rb.status, "done")
        # 验证组合已更新
        updated = self.svc.get_portfolio(created.id)
        self.assertAlmostEqual(updated.totalCapital, 2_000_000)
        self.assertEqual(updated.strategyCount, 2)
        # 验证再平衡历史
        rbs = self.svc.list_rebalances(created.id)
        self.assertTrue(len(rbs) >= 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
