"""AI 每日复盘单元测试（确定性，零外网）。

用临时 SQLite 验证：
- generate_review 产生完整报告
- get_latest 返回最新
- list_reviews 返回历史
- 报告含 pnl/trades/performance/decisions 字段
"""
import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import unittest


class TestDailyReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.database import init_db, SessionLocal
        from app.paper.domain_models import PaperAccount
        init_db()
        db = SessionLocal()
        a = PaperAccount(name="复盘单测", initial_capital=1_000_000.0)
        db.add(a)
        db.commit()
        cls.account_id = a.id
        db.close()

    def setUp(self):
        from app.paper.services.daily_review_service import DailyReviewService
        self.svc = DailyReviewService()

    def test_generate_review(self):
        review = self.svc.generate_review(self.account_id)
        self.assertIsNotNone(review)
        self.assertEqual(review.accountId, self.account_id)
        self.assertTrue(len(review.date) > 0)
        self.assertTrue(len(review.summary) > 0)
        # 检查核心字段
        self.assertIn("todayPnl", review.pnlSummary)
        self.assertIn("totalAssets", review.performance)
        self.assertIn("filledBuys", review.tradesSummary)
        self.assertIsInstance(review.decisions, list)

    def test_get_latest(self):
        self.svc.generate_review(self.account_id)
        latest = self.svc.get_latest(self.account_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.accountId, self.account_id)

    def test_list_reviews(self):
        self.svc.generate_review(self.account_id)
        self.svc.generate_review(self.account_id)  # 第二条
        reviews = self.svc.list_reviews(self.account_id, limit=10)
        self.assertGreaterEqual(len(reviews), 1)

    def test_no_review_returns_none(self):
        from app.paper.domain_models import PaperAccount
        db = __import__("app.db.database", fromlist=["SessionLocal"]).SessionLocal()
        a2 = PaperAccount(name="空账户", initial_capital=500_000.0)
        db.add(a2)
        db.commit()
        aid = a2.id
        db.close()
        self.assertIsNone(self.svc.get_latest(aid))


if __name__ == "__main__":
    unittest.main(verbosity=2)
