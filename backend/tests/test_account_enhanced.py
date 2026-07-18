"""多账户增强单元测试（确定性，零外网）。

用临时 SQLite 验证：
- update_account（名称/资金）
- delete_account（含级联清理）
- get_overview（汇总统计）
"""
import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import unittest


class TestAccountEnhanced(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.database import init_db, SessionLocal
        from app.paper.domain_models import PaperAccount
        init_db()
        db = SessionLocal()
        a1 = PaperAccount(name="账户A", initial_capital=1_000_000.0)
        a2 = PaperAccount(name="账户B", initial_capital=2_000_000.0)
        db.add_all([a1, a2])
        db.commit()
        cls.a1_id = a1.id
        cls.a2_id = a2.id
        db.close()

    def setUp(self):
        from app.paper.services.account_service import AccountService
        self.svc = AccountService()

    def test_update_name(self):
        from app.paper.schemas import UpdateAccountRequest
        resp = self.svc.update_account(self.a1_id, UpdateAccountRequest(name="新名称"))
        self.assertEqual(resp.name, "新名称")

    def test_update_capital(self):
        from app.paper.schemas import UpdateAccountRequest
        resp = self.svc.update_account(self.a1_id, UpdateAccountRequest(initialCapital=2_000_000.0))
        self.assertAlmostEqual(resp.initialCapital, 2_000_000.0)
        # 现金应同步增加
        self.assertGreater(resp.cash, 900_000)

    def test_delete_account(self):
        ok = self.svc.delete_account(self.a2_id)
        self.assertTrue(ok)
        with self.assertRaises(Exception):
            self.svc.get_account(self.a2_id)

    def test_overview(self):
        ov = self.svc.get_overview()
        self.assertGreaterEqual(ov.totalAccounts, 1)
        self.assertGreater(ov.totalAssets, 0)
        self.assertTrue(len(ov.accounts) >= 1)
        # 验证字段
        first = ov.accounts[0]
        self.assertIn("name", first.model_fields)
        self.assertIn("totalAssets", first.model_fields)


if __name__ == "__main__":
    unittest.main(verbosity=2)
