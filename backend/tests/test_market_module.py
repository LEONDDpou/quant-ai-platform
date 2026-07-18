"""市场实时模块单元测试。

覆盖：
  * 行情代码归一化（normalize_code）
  * K 线解析（_parse_kline，westock 收盘列名为 last）
  * 技术指标计算（compute_technicals 字段完整性）
  * AI 量化评分（compute_ai_score 取值区间 + 风险等级 + Pydantic 校验）
  * 可靠性原语（CircuitBreaker / RateLimiter / retry）
  * 多源故障切换（FailoverOrchestrator 降级与全失败熔断）
  * 响应模型（QuoteOut / BreadthOut / SourceHealth）

全部为离线、无网络依赖的纯函数 / 单测，可在 CI 中直接 `pytest backend/tests/test_market_module.py`。
"""
import asyncio
import os
import tempfile
import time

# 隔离测试数据库，避免触碰主库 / market.db
_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp.name}")
os.environ.setdefault("MARKET_DB_URL", f"sqlite+aiosqlite:///{_tmp.name}")

import unittest

from app.market.sources.base import Quote, QuoteSource, normalize_code
from app.market.core.resilience import CircuitBreaker, RateLimiter, retry
from app.market.services.technicals import compute_technicals
from app.market.services.ai_score import compute_ai_score
from app.market.services.kline_service import _parse_kline
from app.market.schemas import AIScoreOut, QuoteOut, BreadthOut, SourceHealth
from app.market.sources.failover import FailoverOrchestrator
from app.market.core.config import MarketSettings


class _FakeSource(QuoteSource):
    """可注入成功/失败的桩数据源，用于验证故障切换。"""

    def __init__(self, fail: bool = False, label: str = "fake"):
        self.name = label
        self._fail = fail
        self.available = True

    async def fetch_quotes(self, codes):
        if self._fail:
            raise RuntimeError(f"{self.name} down")
        return {c: Quote(code=c, name=f"N{c}", price=10.0) for c in codes}


class TestNormalizeCode(unittest.TestCase):
    def test_variants(self):
        self.assertEqual(normalize_code("sh600519"), "600519")
        self.assertEqual(normalize_code("600519.SH"), "600519")
        self.assertEqual(normalize_code("sz000858"), "000858")
        self.assertEqual(normalize_code(" 000001 "), "000001")
        self.assertEqual(normalize_code("bj830799"), "830799")
        # 无法识别时原样返回（统一大写）
        self.assertEqual(normalize_code("abc"), "ABC")


class TestParseKline(unittest.TestCase):
    def test_parse_last_column(self):
        rows = [
            {"date": "2024-01-02", "open": 1, "high": 2, "low": 0.5, "last": 1.5, "volume": 100, "amount": 150},
            # westock 收盘列名为 last；缺省走 close 兜底；open 缺失则回退 close
            {"date": "2024-01-03", "close": 2.0},
        ]
        bars = _parse_kline(rows)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["close"], 1.5)
        self.assertEqual(bars[0]["open"], 1)
        self.assertEqual(bars[1]["close"], 2.0)
        self.assertEqual(bars[1]["open"], 2.0)  # open 缺失回退到 close

    def test_skip_when_no_close(self):
        rows = [{"date": "2024-01-02", "open": 1, "volume": 10}]
        self.assertEqual(_parse_kline(rows), [])


class TestTechnicals(unittest.TestCase):
    def test_keys_present(self):
        closes = list(range(1, 37))  # 36 个采样，足以计算 ma5/10/20 + rsi + macd
        t = compute_technicals(closes)
        for k in ("ma5", "ma10", "ma20", "rsi14", "macd", "macdSignal", "macdHist"):
            self.assertIn(k, t)
        self.assertIsNotNone(t["ma20"])
        self.assertIsNotNone(t["rsi14"])

    def test_short_series_safe(self):
        t = compute_technicals([1.0, 2.0])
        # 数据不足时返回 None，不应抛异常
        self.assertIsNone(t["ma20"])


class TestAIScore(unittest.TestCase):
    def test_score_range_and_high_risk(self):
        q = Quote(code="600519", name="X", price=100, change_pct=10.0, float_mv=1e12)
        sc = compute_ai_score(q, {"main_in": 0.0}, {"rsi14": 85, "ma20": 90})
        self.assertGreaterEqual(sc["score"], 0)
        self.assertLessEqual(sc["score"], 100)
        self.assertEqual(sc["riskLevel"], "high")  # RSI>80 触发高风险
        # Pydantic schema 校验
        AIScoreOut(**sc)

    def test_low_risk(self):
        q = Quote(code="1", name="Y", price=10, change_pct=0.0, float_mv=1e10)
        sc = compute_ai_score(q, {"main_in": 0}, {"rsi14": 50, "ma20": 10})
        self.assertEqual(sc["riskLevel"], "low")

    def test_schema_field_names(self):
        q = Quote(code="t", name="t", price=5, change_pct=1.0, float_mv=1e9)
        sc = compute_ai_score(q, {"main_in": 1e8}, {"rsi14": 55, "ma20": 5})
        for f in ("score", "techScore", "fundScore", "sentimentScore", "momentum", "volatility", "riskLevel"):
            self.assertIn(f, sc)


class TestResilience(unittest.TestCase):
    def test_circuit_breaker_state_machine(self):
        cb = CircuitBreaker("t", fail_threshold=2, cooldown=0.1)
        self.assertTrue(cb.allow())
        cb.record_failure()
        self.assertTrue(cb.allow())  # 阈值未达
        cb.record_failure()
        self.assertFalse(cb.allow())  # 连续 2 次失败 -> OPEN
        time.sleep(0.15)  # 冷却结束 -> HALF_OPEN
        self.assertTrue(cb.allow())

    def test_rate_limiter_blocks_when_empty(self):
        async def go():
            rl = RateLimiter(10.0)
            await rl.acquire(tokens=10.0)  # 抽干令牌桶
            t0 = time.monotonic()
            await rl.acquire(tokens=5.0)   # 需 ~0.5s  refill
            return time.monotonic() - t0
        dt = asyncio.run(go())
        self.assertGreater(dt, 0.3)

    def test_retry_eventually_succeeds(self):
        async def go():
            calls = {"n": 0}

            async def flaky():
                calls["n"] += 1
                if calls["n"] < 3:
                    raise ValueError("boom")
                return "ok"

            return await retry(flaky, attempts=5, base_delay=0.01), calls["n"]
        res, n = asyncio.run(go())
        self.assertEqual(res, "ok")
        self.assertEqual(n, 3)

    def test_retry_exhausted_raises(self):
        async def go():
            async def always():
                raise ValueError("nope")

            try:
                await retry(always, attempts=2, base_delay=0.001)
                return None
            except ValueError:
                return "raised"
        self.assertEqual(asyncio.run(go()), "raised")


class TestFailover(unittest.TestCase):
    def _orch(self, a_fail, b_fail):
        async def go():
            a = _FakeSource(fail=a_fail, label="a")
            b = _FakeSource(fail=b_fail, label="b")
            orch = FailoverOrchestrator(
                [a, b],
                MarketSettings(source_order="a,b", source_retries=1, cb_fail_threshold=5, cb_cooldown=30.0, rate_limit_per_sec=100),
            )
            return orch
        return asyncio.run(go())

    def test_fallthrough_to_next_source(self):
        async def go():
            a = _FakeSource(fail=True, label="a")
            b = _FakeSource(fail=False, label="b")
            orch = FailoverOrchestrator(
                [a, b],
                MarketSettings(source_order="a,b", source_retries=1, rate_limit_per_sec=100),
            )
            res = await orch.get_quotes(["600519"])
            return res, orch.last_source
        res, last = asyncio.run(go())
        self.assertIn("600519", res)
        self.assertEqual(last, "b")

    def test_all_fail_raises_source_unavailable(self):
        orch = self._orch(a_fail=True, b_fail=True)

        async def go():
            try:
                await orch.get_quotes(["600519"])
                return None
            except Exception as e:  # noqa: BLE001
                return type(e).__name__
        self.assertEqual(asyncio.run(go()), "SourceUnavailableError")

    def test_health_report_shape(self):
        orch = self._orch(a_fail=False, b_fail=False)
        rep = orch.health_report()
        self.assertEqual(len(rep), 2)
        self.assertIn("circuit", rep[0])
        self.assertIn("available", rep[0])


class TestSchemas(unittest.TestCase):
    def test_quote_out(self):
        q = QuoteOut(code="600519", name="茅台", price=1253.0, changePct=-0.48, source="tencent")
        self.assertEqual(q.code, "600519")

    def test_breadth_out(self):
        b = BreadthOut(total=100, upCount=60, downCount=30, limitUp=5, limitDown=2, breadthPct=60.0)
        self.assertEqual(b.upCount, 60)

    def test_source_health(self):
        s = SourceHealth(name="tencent", available=True, circuit="closed", lastUsed=True)
        self.assertTrue(s.available)


if __name__ == "__main__":
    unittest.main()
