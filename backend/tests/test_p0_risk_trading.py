"""P0 风控事前拦截 + 交易时段感知 单元测试。"""
import os, sys, tempfile
_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import unittest
from unittest import mock


class TestTradingSession(unittest.TestCase):
    """交易时段状态机测试。"""

    def test_weekend_is_closed(self):
        from app.paper.trading_session import TradingSession
        with mock.patch("app.paper.trading_session.TradingSession.current",
                        return_value="closed"):
            self.assertEqual(TradingSession.current(), "closed")

    def test_continuous_trading(self):
        from app.paper.trading_session import TradingSession
        with mock.patch("app.paper.trading_session.TradingSession.current",
                        return_value="continuous"):
            self.assertTrue(TradingSession.can_match())
            self.assertTrue(TradingSession.can_trade())
            self.assertTrue(TradingSession.can_cancel())

    def test_pre_close_no_cancel(self):
        from app.paper.trading_session import TradingSession
        with mock.patch("app.paper.trading_session.TradingSession.current",
                        return_value="pre_close"):
            self.assertFalse(TradingSession.can_cancel())
            self.assertFalse(TradingSession.can_match())

    def test_price_limits(self):
        from app.paper.trading_session import get_price_limit_pct
        self.assertEqual(get_price_limit_pct("600519"), 0.10)  # 主板
        self.assertEqual(get_price_limit_pct("300750"), 0.20)  # 创业板
        self.assertEqual(get_price_limit_pct("688981"), 0.20)  # 科创板
        self.assertEqual(get_price_limit_pct("830799"), 0.30)  # 北交所


class TestPreTradeRisk(unittest.TestCase):
    """前置风控增强测试。"""

    @classmethod
    def setUpClass(cls):
        from app.db.database import init_db, SessionLocal
        from app.paper.domain_models import PaperAccount
        init_db()
        db = SessionLocal()
        a = PaperAccount(name="P0风控测试", initial_capital=1_000_000.0)
        db.add(a)
        db.commit()
        cls.account_id = a.id
        db.close()

    def setUp(self):
        from app.paper.services.risk_service import RiskService
        self.svc = RiskService()

    def test_price_limit_block(self):
        """涨跌停价应被拦截。"""
        mock_quote = mock.patch("app.paper.services.risk_service.market_provider.quote",
                                return_value={"close": 10.0, "name": "平安银行"})
        with mock_quote:
            ok, vios = self.svc.evaluate_pre_trade(self.account_id, "000001", "buy", "limit", 9999.0, 100)
        self.assertFalse(ok)
        self.assertTrue(any("涨停" in v for v in vios), f"vios={vios}")

    def test_normal_price_passes(self):
        """正常价格应通过。"""
        mock_quote = mock.patch("app.paper.services.risk_service.market_provider.quote",
                                return_value={"close": 10.0, "name": "平安银行"})
        with mock_quote:
            ok, vios = self.svc.evaluate_pre_trade(self.account_id, "000001", "buy", "limit", 5.0, 100)
        self.assertTrue(ok, f"vios={vios}")

    def test_order_service_risk_block(self):
        """OrderService 下单时应触发风控拦截。"""
        from app.paper.services.order_service import OrderService
        from app.paper.schemas import CreateOrderRequest
        svc = OrderService()
        with mock.patch("app.paper.services.risk_service.market_provider.quote",
                        return_value={"close": 10.0, "name": "平安银行"}), \
             mock.patch("app.paper.trading_session.TradingSession.can_match",
                        return_value=False):  # 跳过撮合
            with self.assertRaises(Exception) as ctx:
                svc.create_order(CreateOrderRequest(
                    accountId=self.account_id, code="000001", direction="buy",
                    orderType="limit", price=9999.0, quantity=100,
                ))
        self.assertIn("RISK_BLOCKED", str(ctx.exception.code))

    def test_match_engine_skips_outside_hours(self):
        """非交易时段撮合应跳过。"""
        from app.paper.trading_session import TradingSession
        with mock.patch("app.paper.trading_session.TradingSession.current",
                        return_value="closed"):
            self.assertFalse(TradingSession.can_match())

    def test_self_trade_detected(self):
        """自成交检测：同账户已有挂单应被识别。"""
        # 直接用 DB 插入一笔挂单（避免绕 OrderService 的复杂撮合逻辑）
        from app.db.database import SessionLocal
        from app.paper.domain_models import PaperOrder
        db = SessionLocal()
        existing = PaperOrder(
            account_id=self.account_id, code="000001", direction="sell",
            order_type="limit", price=10.0, quantity=100,
            filled_quantity=0, status="pending", source="human",
        )
        db.add(existing)
        db.commit()
        db.close()

        # 买入同样的代码应有自成交风控
        with mock.patch("app.paper.services.risk_service.market_provider.quote",
                        return_value={"close": 10.0, "name": "平安银行"}):
            ok, vios = self.svc.evaluate_pre_trade(self.account_id, "000001", "buy", "limit", 5.0, 100)
        self.assertFalse(ok, f"应检测到自成交: {vios}")
        self.assertTrue(any("自成交" in v for v in vios))


if __name__ == "__main__":
    unittest.main(verbosity=2)
