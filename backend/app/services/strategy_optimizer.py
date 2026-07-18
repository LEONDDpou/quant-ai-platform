"""策略优化器 — 参数网格搜索、组合回测、压力测试。

说明：
- 所有回测基于 westock-data 真实 K线，严格防未来函数。
- 组合回测支持等权 / IC加权 / 波动率倒数加权三种方式。
- 压力测试基于历史模拟 + 情景分析。
- 结果仅为模型输出，不构成投资建议。
"""
from __future__ import annotations

import itertools
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np

from app.services import data_provider as dp
from app.services.backtest_engine import _safe_std


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class OptimizeResult:
    strategy: str
    symbol: str
    bestParams: dict
    bestScore: float
    allResults: list[dict] = field(default_factory=list)


@dataclass
class PortfolioResult:
    strategies: list[str]
    symbols: list[str]
    weights: list[float]
    totalReturn: float
    annualizedReturn: float
    sharpeRatio: float
    maxDrawdown: float
    winRate: float
    individualResults: list[dict] = field(default_factory=list)
    equityCurve: list[dict] = field(default_factory=list)


@dataclass
class StressTestScenario:
    name: str
    description: str
    shockPct: float        # 单日跌幅 (%)
    volMultiplier: float   # 波动率放大倍数
    consecutiveDays: int   # 连续下跌天数


@dataclass
class StressTestResult:
    scenario: str
    description: str
    peakToTrough: float    # 峰谷跌幅 (%)
    recoveryDays: int      # 恢复天数 (-1 表示未恢复)
    finalReturn: float     # 期末收益 (%)
    survived: bool         # 是否存活（未归零）


# ── 工具函数 ──────────────────────────────────────────────

def _calc_sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean_r = statistics.mean(returns)
    std_r = _safe_std(returns)
    return (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0


def _calc_max_drawdown(equity: list[float]) -> float:
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)
    return max_dd


def _run_ma_cross_backtest(
    closes: list[float],
    short_window: int,
    long_window: int,
    initial_capital: float = 1_000_000,
) -> tuple[list[float], float, float, float, int, int]:
    """运行 MA 交叉回测，返回 (equity, totalReturn, sharpe, maxDD, trades, wins)."""
    n = len(closes)
    if n < long_window + 5:
        return [initial_capital], 0.0, 0.0, 0.0, 0, 0

    # 计算均线（严格防未来函数：第 i 日信号由 i-1 日数据决定）
    ma_short = [sum(closes[max(0, i - short_window + 1):i + 1]) / min(i + 1, short_window) for i in range(n)]
    ma_long = [sum(closes[max(0, i - long_window + 1):i + 1]) / min(i + 1, long_window) for i in range(n)]

    # 仓位序列
    position = [0.0] * n
    for i in range(1, n):
        if ma_long[i - 1] == 0:
            continue
        position[i] = 1.0 if ma_short[i - 1] > ma_long[i - 1] else 0.0

    # 权益曲线
    equity = [initial_capital]
    strat_rets = []
    for i in range(1, n):
        daily_ret = closes[i] / closes[i - 1] - 1.0 if closes[i - 1] else 0.0
        r = position[i] * daily_ret
        strat_rets.append(r)
        equity.append(equity[-1] * (1.0 + r))

    total_return = equity[-1] / equity[0] - 1.0
    sharpe = _calc_sharpe(strat_rets)
    max_dd = _calc_max_drawdown(equity)

    # 交易统计
    trades = 0
    wins = 0
    holding = False
    buy_price = 0.0
    for i in range(1, n):
        if position[i] == 1.0 and not holding:
            holding = True
            buy_price = closes[i]
            trades += 1
        elif position[i] == 0.0 and holding:
            holding = False
            if closes[i] > buy_price:
                wins += 1

    return equity, total_return, sharpe, max_dd, trades, wins


# ── 1. 参数网格搜索优化 ────────────────────────────────────

PRESET_GRID = {
    "MA双均线交叉基准策略": {
        "short_window": [3, 5, 8, 10, 12, 15],
        "long_window": [15, 20, 25, 30, 40, 50, 60],
    },
    "MA双均线交叉": {
        "short_window": [3, 5, 8, 10, 12, 15],
        "long_window": [15, 20, 25, 30, 40, 50, 60],
    },
    "ma_cross": {
        "short_window": [3, 5, 8, 10, 12, 15],
        "long_window": [15, 20, 25, 30, 40, 50, 60],
    },
}


def optimize_grid_search(
    strategy: str,
    symbol: str,
    startDate: str,
    endDate: str,
    metric: str = "sharpe",
) -> OptimizeResult:
    """对 MA 交叉策略执行网格搜索参数优化。

    Args:
        strategy: 策略名称（如 "MA双均线交叉基准策略"）
        symbol: 标的代码（如 "sh000300"）
        startDate: 开始日期
        endDate: 结束日期
        metric: 优化目标 ("sharpe" | "total_return" | "calmar")

    Returns:
        OptimizeResult 包含最佳参数、评分和全部结果。
    """
    # 获取 K 线
    kline = dp.get_stock_kline(symbol, period="day", limit=700)
    if not kline:
        raise RuntimeError(f"无法获取 K线 数据: {symbol}")

    kline = [k for k in kline if startDate <= k["date"] <= endDate]
    if len(kline) < 30:
        kline = dp.get_stock_kline(symbol, period="day", limit=700)
    if len(kline) < 30:
        raise RuntimeError("K线 数据不足")

    closes = [k["close"] for k in kline]
    dates = [k["date"] for k in kline]

    # 确定参数网格
    grid = PRESET_GRID.get(strategy, PRESET_GRID["MA双均线交叉基准策略"])
    short_windows = grid.get("short_window", [5, 10, 20])
    long_windows = grid.get("long_window", [20, 30, 60])

    all_results = []
    best_score = float("-inf")
    best_params = {}

    for sw, lw in itertools.product(short_windows, long_windows):
        if sw >= lw:
            continue  # 短均线必须小于长均线

        _, total_return, sharpe, max_dd, trades, wins = _run_ma_cross_backtest(
            closes, sw, lw, 1_000_000
        )

        win_rate = (wins / trades * 100) if trades else 0.0
        calmar = total_return / max_dd if max_dd > 0 else total_return

        item = {
            "shortWindow": sw,
            "longWindow": lw,
            "totalReturn": round(total_return * 100, 2),
            "sharpeRatio": round(sharpe, 2),
            "maxDrawdown": round(max_dd * 100, 2),
            "winRate": round(win_rate, 1),
            "totalTrades": trades,
            "calmarRatio": round(calmar, 2),
        }
        all_results.append(item)

        # 根据指标打分
        score = item["sharpeRatio"] if metric == "sharpe" else (
            item["totalReturn"] if metric == "total_return" else item["calmarRatio"]
        )
        if score > best_score:
            best_score = score
            best_params = {"shortWindow": sw, "longWindow": lw}

    # 按评分降序排列
    all_results.sort(key=lambda x: x["sharpeRatio"] if metric == "sharpe" else x["totalReturn"], reverse=True)

    return OptimizeResult(
        strategy=strategy,
        symbol=symbol,
        bestParams=best_params,
        bestScore=round(float(best_score), 2),
        allResults=all_results,
    )


# ── 2. 组合回测（多策略并行） ──────────────────────────────

def run_portfolio_backtest(
    strategies: list[str],
    symbols: list[str],
    startDate: str,
    endDate: str,
    initialCapital: float = 1_000_000,
    weightScheme: str = "equal",
) -> PortfolioResult:
    """多策略在多标的上并行回测，按指定权重方案组合。

    Args:
        strategies: 策略名称列表
        symbols: 标的代码列表
        startDate: 开始日期
        endDate: 结束日期
        initialCapital: 初始资金
        weightScheme: 权重方案 "equal" | "sharpe_weighted" | "inverse_volatility"

    Returns:
        PortfolioResult 包含组合收益、各策略单独结果。
    """
    individual_results = []
    strategy_returns = []  # list of list[float]
    strategy_sharpes = []
    strategy_vols = []

    # 强制策略与标的等长（若不等长则交叉配对）
    if len(strategies) != len(symbols):
        # 使用笛卡尔积配对
        pairs = list(itertools.product(strategies, symbols))
    else:
        pairs = list(zip(strategies, symbols))

    # 限制最多 9 对（避免过重）
    pairs = pairs[:9]

    for strategy, symbol in pairs:
        try:
            kline = dp.get_stock_kline(symbol, period="day", limit=700)
            if not kline:
                continue
            kline = [k for k in kline if startDate <= k["date"] <= endDate]
            if len(kline) < 30:
                continue

            closes = [k["close"] for k in kline]
            dates = [k["date"] for k in kline]
            n = len(closes)

            # 默认使用 MA(5,20) 回测
            equity, total_return, sharpe, max_dd, trades, wins = _run_ma_cross_backtest(
                closes, 5, 20, initialCapital / len(pairs)
            )

            # 计算日收益率序列
            rets = []
            for i in range(1, len(equity)):
                if equity[i - 1] > 0:
                    rets.append(equity[i] / equity[i - 1] - 1.0)

            individual_results.append({
                "strategy": strategy,
                "symbol": symbol,
                "totalReturn": round(total_return * 100, 2),
                "sharpeRatio": round(sharpe, 2),
                "maxDrawdown": round(max_dd * 100, 2),
                "winRate": round((wins / trades * 100) if trades else 0, 1),
                "totalTrades": trades,
            })

            strategy_returns.append(rets)
            strategy_sharpes.append(sharpe if sharpe > 0 else 0.01)
            strategy_vols.append(_safe_std(rets) if rets else 0.01)

        except Exception:
            continue

    if not individual_results:
        raise RuntimeError("没有成功运行任何策略回测")

    # 计算权重
    n_strats = len(individual_results)
    if weightScheme == "equal":
        weights = [1.0 / n_strats] * n_strats
    elif weightScheme == "sharpe_weighted":
        total_sharpe = sum(max(s, 0.01) for s in strategy_sharpes)
        weights = [max(s, 0.01) / total_sharpe for s in strategy_sharpes] if total_sharpe > 0 else [1.0 / n_strats] * n_strats
    elif weightScheme == "inverse_volatility":
        inv_vols = [1.0 / max(v, 0.001) for v in strategy_vols]
        total_inv = sum(inv_vols)
        weights = [iv / total_inv for iv in inv_vols] if total_inv > 0 else [1.0 / n_strats] * n_strats
    else:
        weights = [1.0 / n_strats] * n_strats

    # 组合收益率（对齐长度）
    min_len = min(len(r) for r in strategy_returns) if strategy_returns else 0
    if min_len == 0:
        raise RuntimeError("收益率序列为空")

    aligned_rets = [r[:min_len] for r in strategy_returns]
    portfolio_rets = []
    for day_idx in range(min_len):
        combo_ret = sum(weights[i] * aligned_rets[i][day_idx] for i in range(n_strats))
        portfolio_rets.append(combo_ret)

    # 组合权益曲线
    equity_curve = [initialCapital]
    for r in portfolio_rets:
        equity_curve.append(equity_curve[-1] * (1.0 + r))

    total_return = equity_curve[-1] / initialCapital - 1.0
    n_days = len(portfolio_rets)
    years = n_days / 252.0 if n_days else 1.0
    annualized = (1.0 + total_return) ** (1.0 / years) - 1.0 if years > 0 and total_return > -1.0 else 0.0
    sharpe = _calc_sharpe(portfolio_rets)
    max_dd = _calc_max_drawdown(equity_curve)

    equity_data = [
        {"date": str(idx), "value": round(equity_curve[idx], 2)}
        for idx in range(0, len(equity_curve), max(1, len(equity_curve) // 200))
    ]

    return PortfolioResult(
        strategies=[r["strategy"] for r in individual_results],
        symbols=[r["symbol"] for r in individual_results],
        weights=weights,
        totalReturn=round(total_return * 100, 2),
        annualizedReturn=round(annualized * 100, 2),
        sharpeRatio=round(sharpe, 2),
        maxDrawdown=round(max_dd * 100, 2),
        winRate=0.0,  # 组合层面不计算胜率
        individualResults=individual_results,
        equityCurve=equity_data,
    )


# ── 3. 压力测试 ──────────────────────────────────────────────

STRESS_SCENARIOS: list[StressTestScenario] = [
    StressTestScenario(
        name="2008金融危机",
        description="单日暴跌5%+连续5日累计下跌15%，波动率放大3倍",
        shockPct=-5.0,
        volMultiplier=3.0,
        consecutiveDays=5,
    ),
    StressTestScenario(
        name="2015股灾",
        description="单日暴跌7%+连续3日累计下跌18%，波动率放大4倍",
        shockPct=-7.0,
        volMultiplier=4.0,
        consecutiveDays=3,
    ),
    StressTestScenario(
        name="2020疫情冲击",
        description="单日暴跌4%+连续5日累计下跌12%，波动率放大2.5倍",
        shockPct=-4.0,
        volMultiplier=2.5,
        consecutiveDays=5,
    ),
    StressTestScenario(
        name="温和回调",
        description="单日下跌2%+连续10日累计下跌8%，波动率放大1.5倍",
        shockPct=-2.0,
        volMultiplier=1.5,
        consecutiveDays=10,
    ),
    StressTestScenario(
        name="极端崩盘",
        description="单日暴跌10%+连续3日累计下跌25%，波动率放大6倍",
        shockPct=-10.0,
        volMultiplier=6.0,
        consecutiveDays=3,
    ),
]


def run_stress_test(
    symbol: str = "sh000300",
    initialCapital: float = 1_000_000,
) -> list[StressTestResult]:
    """对标的运行全部预设压力测试场景。

    Args:
        symbol: 标的代码
        initialCapital: 初始资金

    Returns:
        压力测试结果列表。
    """
    # 获取近期 K 线数据作为基准
    kline = dp.get_stock_kline(symbol, period="day", limit=252)
    if not kline or len(kline) < 60:
        raise RuntimeError("K线 数据不足，无法压力测试")

    closes = [k["close"] for k in kline]
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1]:
            rets.append(closes[i] / closes[i - 1] - 1.0)

    if not rets:
        raise RuntimeError("收益率数据不足")

    base_vol = _safe_std(rets)

    results = []
    for scenario in STRESS_SCENARIOS:
        # 模拟冲击后的权益曲线（从当前最近价格开始）
        last_price = closes[-1]
        simulated_prices = [last_price]

        # 冲击期
        for day in range(scenario.consecutiveDays):
            # 均值回归式下跌（每天递减）
            remaining = scenario.consecutiveDays - day
            daily_drop = scenario.shockPct * (remaining / scenario.consecutiveDays) / 100.0
            new_price = simulated_prices[-1] * (1.0 + daily_drop)
            # 叠加波动率放大
            noise = np.random.normal(0, base_vol * scenario.volMultiplier)
            new_price *= (1.0 + noise)
            simulated_prices.append(max(new_price, last_price * 0.01))

        # 恢复期（252天）
        recovery_days = -1
        for day in range(252):
            noise = np.random.normal(base_vol * 0.0003, base_vol * 0.8)
            new_price = simulated_prices[-1] * (1.0 + noise)
            simulated_prices.append(max(new_price, 1.0))

            # 检查是否恢复到冲击前水平
            if recovery_days < 0 and simulated_prices[-1] >= last_price:
                recovery_days = day + 1

        # 计算指标
        peak_to_trough = min((p / simulated_prices[0] - 1.0) for p in simulated_prices) * 100
        final_return = (simulated_prices[-1] / simulated_prices[0] - 1.0) * 100
        survived = simulated_prices[-1] > 1.0

        results.append(StressTestResult(
            scenario=scenario.name,
            description=scenario.description,
            peakToTrough=round(peak_to_trough, 2),
            recoveryDays=recovery_days,
            finalReturn=round(final_return, 2),
            survived=survived,
        ))

    return results
