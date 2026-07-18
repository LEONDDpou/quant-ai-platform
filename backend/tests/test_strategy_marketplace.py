"""策略市场单元测试（确定性，零外网）。

用临时 SQLite 验证：
- publish / unpublish / list / search
- subscribe / unsubscribe / get_published_detail
- rate / list_ratings / leaderboard
- 非作者下架拒绝
"""
import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import unittest

from app.paper.errors import PaperError


class TestStrategyMarketplace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.database import init_db, SessionLocal
        from app.paper.domain_models import PaperAccount
        init_db()
        db = SessionLocal()
        # 作者账户
        a1 = PaperAccount(name="作者", initial_capital=1_000_000.0)
        db.add(a1)
        # 订阅者账户
        a2 = PaperAccount(name="订阅者", initial_capital=500_000.0)
        db.add(a2)
        db.commit()
        cls.author_id = a1.id
        cls.subscriber_id = a2.id
        db.close()

    def setUp(self):
        from app.paper.services.strategy_marketplace_service import StrategyMarketplaceService
        self.svc = StrategyMarketplaceService()

    def _publish(self, name="测试策略", source_type="manual", author_id=None, tags=None):
        from app.paper.schemas import PublishStrategyRequest
        return self.svc.publish(PublishStrategyRequest(
            accountId=author_id or self.author_id,
            name=name,
            description="策略描述",
            sourceType=source_type,
            entryRules=[{"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}}],
            exitRules=[{"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}}],
            tags=tags or ["均线", "趋势"],
        ))

    def test_publish_and_list(self):
        self._publish("策略A")
        self._publish("策略B")
        listings = self.svc.list_marketplace()
        self.assertGreaterEqual(len(listings), 2)
        names = [l.name for l in listings]
        self.assertIn("策略A", names)
        self.assertIn("策略B", names)

    def test_search_by_tag(self):
        self._publish("趋势策略", tags=["均线", "趋势"])
        results = self.svc.search_by_tag("趋势")
        self.assertTrue(len(results) >= 1)
        self.assertIn("趋势策略", [r.name for r in results])

    def test_unpublish_author_only(self):
        pub = self._publish("仅作者可下架")
        with self.assertRaises(PaperError):
            self.svc.unpublish(pub.id, 99999)  # 非作者
        ok = self.svc.unpublish(pub.id, self.author_id)
        self.assertTrue(ok)
        # 下架后不出现在浏览列表
        names = [l.name for l in self.svc.list_marketplace()]
        self.assertNotIn("仅作者可下架", names)

    def test_subscribe_and_unsubscribe(self):
        from app.paper.schemas import SubscribeRequest
        pub = self._publish("可订阅策略")
        # 订阅
        result = self.svc.subscribe(SubscribeRequest(
            accountId=self.subscriber_id,
            publishedStrategyId=pub.id,
        ))
        self.assertFalse(result["alreadySubscribed"])
        self.assertIsNotNone(result["localStrategyId"])
        # 重复订阅不应创建新副本
        result2 = self.svc.subscribe(SubscribeRequest(
            accountId=self.subscriber_id,
            publishedStrategyId=pub.id,
        ))
        self.assertTrue(result2["alreadySubscribed"])
        # 取消订阅
        ok = self.svc.unsubscribe(self.subscriber_id, pub.id)
        self.assertTrue(ok)

    def test_rate_and_leaderboard(self):
        from app.paper.schemas import StrategyRatingRequest
        pub = self._publish("评分策略")
        # 评分
        rating = self.svc.rate(StrategyRatingRequest(
            accountId=self.subscriber_id,
            publishedStrategyId=pub.id,
            score=5,
            review="优秀策略",
        ))
        self.assertEqual(rating.score, 5)
        self.assertEqual(rating.review, "优秀策略")
        # 列表
        ratings = self.svc.list_ratings(pub.id)
        self.assertEqual(len(ratings), 1)
        # 排行榜
        lb = self.svc.get_leaderboard(limit=10)
        self.assertTrue(len(lb) >= 1)
        top = next(e for e in lb if e.publishedStrategyId == pub.id)
        self.assertEqual(top.avgRating, 5.0)
        self.assertEqual(top.ratingCount, 1)

    def test_get_detail(self):
        pub = self._publish("详情策略")
        detail = self.svc.get_published_detail(pub.id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.name, "详情策略")

    def test_my_published(self):
        self._publish("我的策略", author_id=self.author_id)
        mine = self.svc.list_my_published(self.author_id)
        self.assertTrue(len(mine) >= 1)
        names = [m.name for m in mine]
        self.assertIn("我的策略", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
