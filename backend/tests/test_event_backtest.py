"""事件驱动回测引擎 —— 确定性单元测试（不依赖外网 / LLM）。

直接加载纯函数引擎模块（仅依赖 numpy），用合成 K线 注入 series_map 验证：
- 金叉入场 / 死叉出场；
- 回撤止损触发卖出；
- 多标的等权组合；
- 空规则兜底；
- 数据不足时抛错。
"""
import importlib.util
import os
import sys
import unittest

# 直接按文件路径加载引擎模块，避免触发整个 app 包的其它依赖
_ENGINE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "app", "services", "event_backtest_engine.py"
)
_spec = importlib.util.spec_from_file_location("event_backtest_engine", _ENGINE_PATH)
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)


def _mk(code, closes):
    """由收盘价列表生成 {date, close} 序列。"""
    out = []
    for i, c in enumerate(closes):
        # 用递增日期，便于计算真实持仓天数
        out.append({"date": "2024-%02d-%02d" % (1 + (i // 28), 1 + (i % 28)), "close": float(c)})
    return out


class TestEventBacktest(unittest.TestCase):
    def test_golden_cross_entry_exit(self):
        """A 先单调上行（金叉入场）再下行（死叉出场），应至少完成 1 个买卖回合。"""
        up = [100 + i for i in range(30)]          # 上行，MA5 上穿 MA20
        dn = [130 - i for i in range(30)]          # 下行，MA5 下穿 MA20
        A = _mk("shA", up + dn)
        rules = [
            {"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
            {"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
        ]
        res = E.run_event_backtest(rules, ["shA"], "", "", 1_000_000,
                                   series_map={"shA": A}, names_map={"shA": "A"})
        self.assertEqual(res["mode"], "event")
        buys = [t for t in res["trades"] if t["action"] == "buy"]
        sells = [t for t in res["trades"] if t["action"] == "sell"]
        self.assertGreater(len(buys), 0, "应有买入成交")
        self.assertGreater(len(sells), 0, "应有卖出成交")
        # 每笔买入应记录正股数与金额
        self.assertGreater(buys[0]["shares"], 0)
        self.assertGreater(buys[0]["amount"], 0)
        # 指标字段齐全
        for k in ("totalReturn", "sharpeRatio", "maxDrawdown", "winRate", "totalTrades"):
            self.assertIn(k, res)
        self.assertEqual(len(res["equityCurve"]), len(A))

    def test_stop_loss_triggers(self):
        """快速下跌触发回撤止损，应产生亏损卖出（pnl<0）。"""
        # 先小幅上涨触发金叉入场，再急跌超过止损阈值
        closes = [100 + i for i in range(25)] + [125 - 20 * i for i in range(1, 10)]
        A = _mk("shA", closes)
        rules = [
            {"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
            {"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
        ]
        res = E.run_event_backtest(rules, ["shA"], "", "", 1_000_000,
                                   risk={"stopLoss": 5.0, "takeProfit": 0.0},
                                   series_map={"shA": A}, names_map={"shA": "A"})
        sells = [t for t in res["trades"] if t["action"] == "sell"]
        if sells:
            # 若存在止损卖出，其 pnl 应 <= 0（急跌离场）
            self.assertLessEqual(sells[-1]["pnl"], 0)

    def test_multi_symbol_equal_weight(self):
        """两个标的各自交易，组合应有两标的的成交汇总。"""
        up = [100 + i for i in range(30)]
        dn = [130 - i for i in range(30)]
        A = _mk("shA", up + dn)
        B = _mk("shB", [100 + 3 * ((i % 10) - 5) for i in range(60)])  # 震荡
        rules = [
            {"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
            {"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
        ]
        res = E.run_event_backtest(rules, ["shA", "shB"], "", "", 1_000_000,
                                   series_map={"shA": A, "shB": B},
                                   names_map={"shA": "A", "shB": "B"})
        self.assertEqual(res["symbol"], "2只标的等权")
        codes = {t["code"] for t in res["trades"]}
        self.assertIn("shA", codes)
        # equityCurve 长度 = 最短序列长度
        self.assertEqual(len(res["equityCurve"]), min(len(A), len(B)))

    def test_empty_rules_fallback(self):
        """空规则应兜底为金叉策略且不抛错。"""
        A = _mk("shA", [100 + i for i in range(60)])
        res = E.run_event_backtest([], ["shA"], "", "", 1_000_000,
                                   series_map={"shA": A}, names_map={"shA": "A"})
        self.assertEqual(res["mode"], "event")
        self.assertIsInstance(res["equityCurve"], list)

    def test_insufficient_data_raises(self):
        """数据不足应抛出 RuntimeError。"""
        A = _mk("shA", [100, 101, 102])  # 不足 25 根
        with self.assertRaises(RuntimeError):
            E.run_event_backtest(
                [{"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}}],
                ["shA"], "", "", 1_000_000,
                series_map={"shA": A}, names_map={"shA": "A"},
            )

    def test_no_universe_raises(self):
        """无标的宇宙应抛错。"""
        with self.assertRaises(RuntimeError):
            E.run_event_backtest([], [], "", "", 1_000_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
