"""回测引擎 — 基于 westock-data 真实 K线 的均线交叉策略。

说明：
- 策略：MA(5) 上穿 MA(20) 全仓买入，下穿全仓卖出（日频，T+1 友好）。
- 严格防未来函数：第 i 日的仓位由 i-1 日及之前的均线决定，收益率用 i-1→i 的
  真实收盘价差，绝不使用当日信号交易当日。
- 无真实账户/选股，纯历史 K线 回测，结果仅为模型输出，不构成投资建议。
"""
import math
from typing import Optional

import numpy as np
from scipy import stats

from app.services import data_provider as dp

# 股票池 → 代表性标的（无真实组合时用作回测标的）
POOL_MAP = {
    "沪深300": "sh000300",
    "中证500": "sh000905",
    "创业板": "sz399006",
    "全部A股": "sh000300",
    "自选股": "sh000300",
}


def _safe_std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(var)


def _factor_timing_position(closes: list[float], factor: str, n: int) -> list[float]:
    """计算因子择时仓位序列（防未来函数：第 i 日仓位由 i-1 日及之前信号决定）。

    各因子择时规则（移植/对齐 QuantsPlaybook 因子定义）：
    - momentum：20 日收益率 > 0（趋势延续）持仓；
    - reversal：近 5 日收益 < 0（超跌，均值回归）持仓；
    - ma_conv：(MA5-MA60)/MA60 > 0（短线上穿、多头排列）持仓；
    - idio_vol：特质波动率低于其自身滚动中位数（低波动regime）持仓。
    """
    position = [0.0] * n
    c = np.array(closes, dtype=float)

    if factor == "momentum":
        n_mom = 20
        sig = np.zeros(n)
        for i in range(n):
            if i - 1 - n_mom >= 0 and closes[i - 1]:
                sig[i] = closes[i - 1] / closes[i - 1 - n_mom] - 1.0
        for i in range(1, n):
            position[i] = 1.0 if sig[i - 1] > 0 else 0.0

    elif factor == "reversal":
        k = 5
        sig = np.zeros(n)
        for i in range(n):
            if i - 1 - k >= 0 and closes[i - 1]:
                sig[i] = closes[i - 1] / closes[i - 1 - k] - 1.0
        # 反转：近期下跌（收益<0）更可能在未来反弹 → 持有
        for i in range(1, n):
            position[i] = 1.0 if sig[i - 1] < 0 else 0.0

    elif factor == "ma_conv":
        ma5 = np.array([sum(closes[max(0, i - 5 + 1):i + 1]) / min(i + 1, 5) for i in range(n)])
        ma60 = np.array([sum(closes[max(0, i - 60 + 1):i + 1]) / min(i + 1, 60) for i in range(n)])
        for i in range(1, n):
            if ma60[i - 1]:
                position[i] = 1.0 if (ma5[i - 1] - ma60[i - 1]) / ma60[i - 1] > 0 else 0.0

    elif factor == "icu_ma":
        # ICU 均线择时（移植自 QuantsPlaybook C-择时类/ICU均线：Siegel 重复中位数斜率回归）
        position = _icu_ma_position(closes, n, N=20)

    elif factor == "idio_vol":
        # 特质波动率（兜底定义：个股收益对 MA20 趋势偏离的 60 日滚动波动，年化）
        stock_ret = np.diff(c) / c[:-1]
        stock_ret = np.concatenate([[0.0], stock_ret])
        trend = np.array([sum(stock_ret[max(0, i - 20 + 1):i + 1]) / min(i + 1, 20) for i in range(n)])
        resid = stock_ret - trend
        win = 60
        iv = np.full(n, np.nan)
        for i in range(n):
            if i - win + 1 < 0:
                continue
            seg = resid[i - win + 1:i + 1]
            if np.isfinite(seg).sum() < 30:
                continue
            iv[i] = float(np.std(seg[np.isfinite(seg)], ddof=1) * math.sqrt(252))
        # 低波动 regime：当前特质波动率低于其历史滚动中位数 → 持有
        for i in range(1, n):
            if not np.isfinite(iv[i - 1]):
                continue
            hist = iv[:i]
            hist = hist[np.isfinite(hist)]
            if len(hist) < 30:
                continue
            med = float(np.median(hist))
            if med > 0:
                position[i] = 1.0 if iv[i - 1] < med else 0.0

    return position


def _icu_ma_position(closes: list[float], n: int, N: int = 20) -> list[float]:
    """ICU 均线择时仓位（忠实移植自 QuantsPlaybook C-择时类/ICU均线）。

    ICU 均线 = 对窗口 N 内收盘价做 Siegel 重复中位数斜率回归（scipy.siegelslopes），
    取回归线末端值 intercept + slope*(N-1) 作为该日的 ICU 均线。
    策略：收盘价上穿 ICU 均线 -> 持有；下穿 -> 空仓（T日收盘信号，T+1 交易，防未来函数）。
    """
    c = np.array(closes, dtype=float)
    icu = [np.nan] * n
    for i in range(N - 1, n):
        w = c[i - N + 1 : i + 1]
        if len(w) == N and np.all(np.isfinite(w)):
            try:
                res = stats.siegelslopes(w, np.arange(N))
                icu[i] = res.intercept + res.slope * (N - 1)
            except Exception:
                icu[i] = c[i]
        else:
            icu[i] = c[i]

    # 仓位：第 i 日由 i-1 日及之前数据决定（close 与 icu 均在 i-1 收盘可得）
    position = [0.0] * n
    prev = 0.0
    for i in range(1, n):
        if i - 1 >= N - 1 and np.isfinite(icu[i - 1]):
            diff_now = c[i - 1] - icu[i - 1]
            diff_prev = (c[i - 2] - icu[i - 2]) if (i - 2 >= N - 1 and np.isfinite(icu[i - 2])) else 0.0
            if diff_now > 0 and diff_prev <= 0:
                prev = 1.0  # 上穿 -> 买入
            elif diff_now < 0 and diff_prev >= 0:
                prev = 0.0  # 下穿 -> 卖出
        position[i] = prev
    return position


def run_backtest(
    strategy: str,
    startDate: str,
    endDate: str,
    stockPool: str,
    initialCapital: float,
    code: Optional[str] = None,
) -> dict:
    """运行真实数据回测，返回 BacktestResult 结构。"""
    symbol = code or POOL_MAP.get(stockPool, "sh000300")
    ws_code = dp.to_westock_code(symbol)
    display_code = ws_code  # 如 sh000300

    # 取足够长的历史以覆盖回测区间
    kline = dp.get_stock_kline(symbol, period="day", limit=700)
    if not kline:
        raise RuntimeError("无法获取回测标的 K线 数据")

    # 按日期过滤
    kline = [k for k in kline if startDate <= k["date"] <= endDate]
    if len(kline) < 30:
        # 放宽到全部可用数据，避免区间过窄
        kline = dp.get_stock_kline(symbol, period="day", limit=700)
    if len(kline) < 25:
        raise RuntimeError("K线 数据不足，无法回测")

    closes = [k["close"] for k in kline]
    dates = [k["date"] for k in kline]
    n = len(closes)

    # 均线
    ma5 = [sum(closes[max(0, i - 5 + 1):i + 1]) / min(i + 1, 5) for i in range(n)]
    ma20 = [sum(closes[max(0, i - 20 + 1):i + 1]) / min(i + 1, 20) for i in range(n)]

    # 仓位序列（防未来函数：第 i 日仓位由 i-1 日及之前的信息决定）
    strategy_key = (strategy or "")
    # 因子择时策略识别（关键词 → 因子名，对齐 QuantsPlaybook 因子定义）
    timing_map = [
        ("ICU均线", "icu_ma"),
        ("ICU", "icu_ma"),
        ("动量因子", "momentum"),
        ("反转因子", "reversal"),
        ("特质波动率", "idio_vol"),
        ("特质波动", "idio_vol"),
        ("均线收敛", "ma_conv"),
    ]
    timing_factor = None
    for kw, fac in timing_map:
        if kw in strategy_key:
            timing_factor = fac
            break

    if timing_factor:
        # 因子择时策略（移植自 QuantsPlaybook 因子定义，严格防未来函数）
        position = _factor_timing_position(closes, timing_factor, n)
    else:
        # 默认：MA(5) 上穿 MA(20) 全仓买入，下穿全仓卖出
        position = [0.0] * n
        for i in range(1, n):
            if ma20[i - 1] == 0:
                continue
            position[i] = 1.0 if ma5[i - 1] > ma20[i - 1] else 0.0

    # 权益曲线
    equity = [initialCapital]
    strat_rets = []
    trades = []
    holding = False
    buy_date = None
    buy_price = 0.0
    hold_days_total = 0
    round_trips = 0
    wins = 0

    for i in range(1, n):
        daily_ret = closes[i] / closes[i - 1] - 1 if closes[i - 1] else 0.0
        r = position[i] * daily_ret
        strat_rets.append(r)
        equity.append(equity[-1] * (1 + r))

        # 成交记录
        if position[i] == 1 and not holding:
            holding = True
            buy_date = dates[i]
            buy_price = closes[i]
            trades.append({
                "date": dates[i], "code": display_code, "name": display_code,
                "action": "buy", "price": round(closes[i], 2),
                "shares": int(initialCapital // closes[i]) if closes[i] else 0,
                "amount": int(initialCapital),
            })
        elif position[i] == 0 and holding:
            holding = False
            sell_price = closes[i]
            pnl = (sell_price - buy_price) * (int(initialCapital // buy_price) if buy_price else 0)
            hold_days_total += (len([d for d in dates if buy_date <= d <= dates[i]]) - 1)
            round_trips += 1
            if sell_price > buy_price:
                wins += 1
            trades.append({
                "date": dates[i], "code": display_code, "name": display_code,
                "action": "sell", "price": round(sell_price, 2),
                "shares": int(initialCapital // buy_price) if buy_price else 0,
                "amount": int(initialCapital),
                "pnl": round(pnl, 2),
            })
            buy_date = None
            buy_price = 0.0

    # 指标
    total_return = equity[-1] / equity[0] - 1
    n_days = len(strat_rets)
    years = n_days / 252.0 if n_days else 1
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else 0.0

    mean_r = sum(strat_rets) / n_days if n_days else 0.0
    std_r = _safe_std(strat_rets)
    sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0

    # 最大回撤
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)

    win_rate = (wins / round_trips * 100) if round_trips else 0.0
    avg_hold = (hold_days_total / round_trips) if round_trips else 0.0

    return {
        "strategyName": strategy,
        "symbol": display_code,
        "startDate": dates[0],
        "endDate": dates[-1],
        "totalReturn": round(total_return * 100, 2),
        "annualizedReturn": round(annualized * 100, 2),
        "sharpeRatio": round(sharpe, 2),
        "maxDrawdown": round(max_dd * 100, 2),
        "winRate": round(win_rate, 1),
        "totalTrades": len(trades),
        "avgHoldDays": round(avg_hold, 1),
        "equityCurve": [{"date": dates[i], "value": round(equity[i], 2)} for i in range(n)],
        "trades": trades,
        "dataSource": "westock",
    }
