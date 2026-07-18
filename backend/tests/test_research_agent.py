"""研究员 Agent 单元测试（确定性，零外网）。

用临时 SQLite + mock 掉 K 线取数，验证：
- run_research 能挖出因子并生成事件驱动策略想法（规则模式）；
- 想法含合法的入场/出场规则；
- backtest_idea 能贯通 M181 事件回测引擎并标记 backtested；
- 会话/想法列举与删除正常。
"""
import os
import sys
import tempfile
import types

# 必须在导入任何 app 模块前设置临时数据库
_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import unittest
from unittest import mock

# 合成 K 线：构造不同走势，确保因子有区分度
def _fake_kline(code, period="day", limit=120):
    n = 80
    if code.endswith("519") or "600519" in code:
        # 上行 + 波动
        closes = [100 + i * 0.6 + (i % 5) for i in range(n)]
    elif code.endswith("750") or "300750" in code:
        # 下行
        closes = [200 - i * 0.5 for i in range(n)]
    else:
        closes = [150 + 3 * ((i * 7) % 11 - 5) for i in range(n)]
    return [
        {"date": f"2024-01-{i+1:02d}", "open": c, "close": c, "high": c + 1, "low": c - 1, "volume": 1000 + i * 10}
        for i, c in enumerate(closes)
    ]


class TestResearchAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.database import init_db, SessionLocal
        from app.paper.domain_models import PaperAccount
        init_db()
        cls.SessionLocal = SessionLocal
        db = SessionLocal()
        acc = PaperAccount(name="研究员单测账户", initial_capital=1_000_000.0)
        db.add(acc)
        db.commit()
        cls.account_id = acc.id
        db.close()

    def _svc(self):
        from app.paper.services.research_service import ResearcherAgentService
        return ResearcherAgentService()

    @mock.patch("app.services.data_provider.get_stock_kline", side_effect=_fake_kline)
    @mock.patch("app.paper.services.research_service.llm.is_llm_enabled", return_value=False)
    def test_run_research(self, *_):
        svc = self._svc()
        from app.paper.schemas import RunResearchRequest
        res = svc.run_research(RunResearchRequest(
            accountId=self.account_id,
            universe=["600519", "300750", "601318"],
            useLlm=False,
            maxIdeas=3,
        ))
        self.assertGreater(res.factorCount, 0, "应挖出因子")
        self.assertGreater(res.ideaCount, 0, "应生成策略想法")
        self.assertEqual(res.session.mode, "rule")
        # 想法需含合法入场/出场规则
        self.assertTrue(len(res.session.ideas) > 0)
        for idea in res.session.ideas:
            self.assertTrue(len(idea.entryRules) > 0)
            self.assertTrue(len(idea.exitRules) > 0)
            for r in idea.entryRules + idea.exitRules:
                self.assertIn(r["kind"], {"ma_cross", "price_breakout", "rsi", "drawdown_stop", "take_profit", "hold_days"})

    @mock.patch("app.services.data_provider.get_stock_kline", side_effect=_fake_kline)
    @mock.patch("app.paper.services.research_service.llm.is_llm_enabled", return_value=False)
    def test_backtest_idea(self, *_):
        svc = self._svc()
        from app.paper.schemas import RunResearchRequest
        res = svc.run_research(RunResearchRequest(
            accountId=self.account_id, universe=["600519", "300750"], useLlm=False, maxIdeas=2,
        ))
        idea = res.session.ideas[0]
        # 回测贯通（run_event 内部也会拉 K 线，已 mock）
        resp = svc.backtest_idea(idea.id, self.account_id)
        self.assertIsNotNone(resp.id)
        # 回测后想法应被标记
        updated = svc.get_idea(idea.id)
        self.assertTrue(updated.backtested)
        self.assertEqual(updated.backtestRunId, resp.id)

    @mock.patch("app.services.data_provider.get_stock_kline", side_effect=_fake_kline)
    @mock.patch("app.paper.services.research_service.llm.is_llm_enabled", return_value=False)
    def test_list_and_delete(self, *_):
        svc = self._svc()
        from app.paper.schemas import RunResearchRequest
        svc.run_research(RunResearchRequest(accountId=self.account_id, universe=["600519"], useLlm=False, maxIdeas=1))
        sessions = svc.list_sessions(self.account_id)
        self.assertTrue(len(sessions) >= 1)
        ideas = svc.list_ideas(self.account_id)
        self.assertTrue(len(ideas) >= 1)
        # 删除第一条想法
        before = len(svc.list_ideas(self.account_id))
        ok = svc.delete_idea(ideas[0].id)
        self.assertTrue(ok)
        after = len(svc.list_ideas(self.account_id))
        self.assertEqual(after, before - 1)

    def test_empty_universe_fallback(self):
        """空宇宙应回退默认观察池，仍能跑出结果（不抛错）。"""
        svc = self._svc()
        from app.paper.schemas import RunResearchRequest
        with mock.patch("app.services.data_provider.get_stock_kline", side_effect=_fake_kline), \
             mock.patch("app.paper.services.research_service.llm.is_llm_enabled", return_value=False):
            res = svc.run_research(RunResearchRequest(accountId=None, universe=[], useLlm=False, maxIdeas=2))
        self.assertIsNotNone(res.session)
        self.assertGreaterEqual(res.factorCount, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
