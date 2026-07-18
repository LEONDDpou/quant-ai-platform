"""事件驱动回测 —— 集成冒烟（打运行中的 :8000 后端，urllib 直连）。

链路：取/建账户 → GET 事件策略模板 → POST 事件回测（多标的）→ GET runs（含 event 模式）→ 下载产物。
任一环节非 200 即报错。不依赖外网（K线 失败时自动 mock 兜底）。
"""
import json
import os
import sys
import unittest
import urllib.request

BASE = "http://localhost:8000"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from app.db.database import init_db, SessionLocal  # noqa: E402
from app.paper.domain_models import PaperAccount  # noqa: E402


def _req(method, path, data=None, timeout=60):
    url = BASE + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        # 产物下载（HTML/CSV/JSON 文件）可能不是 JSON，按原样返回
        try:
            return resp.status, json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return resp.status, raw


def _get_or_create_account():
    _, accounts = _req("GET", "/api/paper/account")
    if accounts:
        return accounts[0]["id"]
    _, acc = _req("POST", "/api/paper/account", {
        "name": "事件回测冒烟账户", "initialCapital": 1000000.0, "baseCurrency": "CNY",
    })
    return acc["id"]


class EventBacktestSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.account_id = _get_or_create_account()

    def test_01_event_strategies(self):
        status, body = _req("GET", "/api/paper/backtest/event-strategies")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(body), 1)
        print(f"[smoke] event-strategies count={len(body)}")

    def test_02_run_event_backtest(self):
        rules = [
            {"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
            {"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
        ]
        status, body = _req("POST", "/api/paper/backtest/event-backtest", {
            "accountId": self.account_id,
            "strategyName": "冒烟-双均线事件",
            "universe": ["sh600519", "sz000858"],
            "initialCapital": 1000000.0,
            "rules": rules,
            "risk": {"stopLoss": 8.0, "takeProfit": 25.0},
        })
        self.assertEqual(status, 200)
        self.assertIn("id", body)
        self.assertEqual(body.get("mode"), "event")
        self.assertIsInstance(body.get("equityCurve"), list)
        self.assertIn("totalReturn", body)
        EventBacktestSmoke.run_id = body["id"]
        print(f"[smoke] event-backtest run_id={body['id']} mode={body.get('mode')} "
              f"symbol={body.get('symbol')} trades={body.get('totalTrades')}")

    def test_03_runs_contains_event(self):
        status, body = _req("GET", f"/api/paper/backtest/runs?account_id={self.account_id}")
        self.assertEqual(status, 200)
        modes = [r.get("mode") for r in body]
        self.assertIn("event", modes)
        print(f"[smoke] runs count={len(body)} modes={set(modes)}")

    def test_04_download_report(self):
        run_id = getattr(EventBacktestSmoke, "run_id", None)
        self.assertIsNotNone(run_id)
        for fname in ("index.html", "summary.json", "equity.csv", "trades.csv"):
            status, _ = _req("GET", f"/api/paper/backtest/runs/{run_id}/file/{fname}")
            self.assertEqual(status, 200, f"下载 {fname} 失败")
        print(f"[smoke] 产物下载 OK run_id={run_id}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
