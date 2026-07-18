"""事件驱动回测引擎 — 多标的、由离散事件触发买卖的组合级回测。

与 M8 单标的「因子/均线」回测的本质差异：
- 一次回测可覆盖**多个标的**（universe），按**等权**构建组合净值；
- 买卖不再由单一预设策略决定，而是由一组**事件规则**驱动：
  * 入场事件（entry）：金叉 / 价格突破 N 日新高 / RSI 超卖 …
  * 出场事件（exit）：死叉 / RSI 超买 / 回撤止损 / 盈利止盈 / 持仓天数超限 …
- 严格防未来函数：第 i 日的仓位由 i-1 日及之前的数据决定，绝不用当日信号交易当日；
- 纯历史 K线 回测，不依赖任何外网 LLM；结果为模型输出，不构成投资建议。

设计要点（与 M8 保持一致的风险/收益口径）：
- 每个标的独立维护 0/1 多头仓位序列 ``position_s[i]``（由 i-1 及之前信息决定）；
- 组合日收益 = (1 / 当前持仓标的数) * Σ_s position_s[i] * 标的日收益；
- 净值曲线按「交易日索引」对齐（截断到最短序列），等权分母恒为有效标的数。
"""
from typing import List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# 指标与小工具（全部基于「截至某索引的闭区间」计算，天然防未来函数）
# ---------------------------------------------------------------------------
def _ma(closes: List[float], i: int, window: int) -> float:
    """计算截至索引 i（含）的 window 日简单移动平均；数据不足返回 0.0。"""
    if i < 0 or window <= 0:
        return 0.0
    lo = max(0, i - window + 1)
    seg = closes[lo : i + 1]
    if not seg:
        return 0.0
    return sum(seg) / len(seg)


def _rsi(closes: List[float], i: int, period: int = 14) -> float:
    """截至索引 i（含）的简易 RSI（基于涨跌均值）。无数据返回 50.0。"""
    if i < period or period <= 0:
        return 50.0
    seg = closes[max(0, i - period) : i + 1]
    gains, losses = [], []
    for j in range(1, len(seg)):
        d = seg[j] - seg[j - 1]
        (gains if d >= 0 else losses).append(abs(d))
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _safe_std(vals: List[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return float(np.sqrt(var))


def _rule_fires(kind: str, params: dict, closes: List[float], i: int) -> bool:
    """判断在第 i 日（用 i-1 及之前数据）是否触发某条规则。

    约定：调用方传入 ``i`` 表示「要在第 i 日做决策」，引擎只看 ``closes[:i]``
    （即索引 0..i-1 的收盘价），从而严格避免未来函数。
    """
    if i < 2:
        return False
    # 以下均使用「截至 i-1」的信息
    if kind == "ma_cross":
        fast = int(params.get("fast", 5))
        slow = int(params.get("slow", 20))
        ma_f_now = _ma(closes, i - 1, fast)
        ma_s_now = _ma(closes, i - 1, slow)
        ma_f_prev = _ma(closes, i - 2, fast)
        ma_s_prev = _ma(closes, i - 2, slow)
        if ma_s_now == 0 or ma_s_prev == 0:
            return False
        # 金叉：快线由下向上穿越慢线
        return ma_f_prev <= ma_s_prev and ma_f_now > ma_s_now
    if kind == "price_breakout":
        window = int(params.get("window", 20))
        if i - 1 < window:
            return False
        lookback = closes[i - 1 - window : i - 1]  # i-1 之前的 window 根
        if not lookback:
            return False
        return closes[i - 1] > max(lookback)
    if kind == "rsi":
        period = int(params.get("period", 14))
        threshold = float(params.get("threshold", 30))
        rsi_now = _rsi(closes, i - 1, period)
        # 超卖（低于阈值）视为触发
        return rsi_now < threshold
    # drawdown_stop / take_profit / hold_days 属于「持仓期动态判定」，不在入场规则内
    return False


def _exit_fires(
    kind: str,
    params: dict,
    closes: List[float],
    i: int,
    entry_price: float,
    peak: float,
    hold_bars: int,
) -> bool:
    """判断在第 i 日（持仓中）是否触发出场。

    ``hold_bars`` = 已持仓的 K线 根数（不含入场当日）。
    """
    if kind == "ma_cross":
        fast = int(params.get("fast", 5))
        slow = int(params.get("slow", 20))
        ma_f_now = _ma(closes, i - 1, fast)
        ma_s_now = _ma(closes, i - 1, slow)
        ma_f_prev = _ma(closes, i - 2, fast)
        ma_s_prev = _ma(closes, i - 2, slow)
        if ma_s_now == 0 or ma_s_prev == 0:
            return False
        # 死叉：快线由上向下穿越慢线
        return ma_f_prev >= ma_s_prev and ma_f_now < ma_s_now
    if kind == "price_breakout":
        window = int(params.get("window", 20))
        if i - 1 < window:
            return False
        lookback = closes[i - 1 - window : i - 1]
        if not lookback:
            return False
        # 跌破 N 日最低 → 出场（反向突破）
        return closes[i - 1] < min(lookback)
    if kind == "rsi":
        period = int(params.get("period", 14))
        threshold = float(params.get("threshold", 30))
        rsi_now = _rsi(closes, i - 1, period)
        # 超买（高于 100-阈值）视为触发
        return rsi_now > (100.0 - threshold)
    if kind == "drawdown_stop":
        pct = float(params.get("pct", 8.0))
        if peak <= 0:
            return False
        return closes[i - 1] < peak * (1.0 - pct / 100.0)
    if kind == "take_profit":
        pct = float(params.get("pct", 20.0))
        if entry_price <= 0:
            return False
        return closes[i - 1] > entry_price * (1.0 + pct / 100.0)
    if kind == "hold_days":
        days = int(params.get("days", 20))
        return hold_bars >= days
    return False


# ---------------------------------------------------------------------------
# 单标的事件驱动回测
# ---------------------------------------------------------------------------
def _backtest_single(
    code: str,
    name: str,
    series: List[dict],
    entry_rules: List[dict],
    exit_rules: List[dict],
    risk: dict,
    weight: float,
    capital_unit: float,
) -> dict:
    """对单个标的跑事件驱动回测，返回该标的的仓位序列、日收益贡献与成交记录。

    ``weight`` 为该标的在组合中的等权权重（= 1 / 有效标的数）；
    ``capital_unit`` 为该标的分配的资金（= 初始资金 * weight），用于计算股数与盈亏。
    返回：``position``(list[0/1])、``contrib``(list[float]，组合日收益贡献)、
          ``trades``(list[dict])。
    """
    closes = [float(k.get("close", 0.0)) for k in series]
    n = len(closes)
    position = [0.0] * n
    contrib = [0.0] * n
    trades: List[dict] = []

    stop_loss = float(risk.get("stopLoss", 0.0) or 0.0)
    take_profit = float(risk.get("takeProfit", 0.0) or 0.0)
    # 把全局风控里的止损/止盈也转成出场规则（与 exit_rules 并列判定）
    dyn_exit_rules = list(exit_rules)
    if stop_loss > 0:
        dyn_exit_rules.append({"kind": "drawdown_stop", "params": {"pct": stop_loss}})
    if take_profit > 0:
        dyn_exit_rules.append({"kind": "take_profit", "params": {"pct": take_profit}})

    holding = False
    entry_price = 0.0
    entry_i = 0
    peak = 0.0
    entry_shares = 0

    for i in range(1, n):
        # 第 i 日决策仅用 closes[:i]（i-1 及之前）
        enter_event = any(_rule_fires(r["kind"], r.get("params", {}), closes, i) for r in entry_rules)
        # 持仓期动态出场判定（需要 entry_price / peak / hold_bars）
        exit_event = False
        if holding:
            hold_bars = i - entry_i - 1  # 不含入场当日
            # A 股 T+1 规则：当日买入不可卖出（#P2）
            if hold_bars < 1:
                exit_event = False
            else:
                exit_event = any(
                _exit_fires(
                    r["kind"], r.get("params", {}), closes, i,
                    entry_price, peak, hold_bars,
                )
                for r in dyn_exit_rules
            )

        if not holding and enter_event:
            # 入场：以第 i 日收盘价成交，股数 = 分配资金 // 入场价
            holding = True
            entry_price = closes[i]
            entry_i = i
            peak = closes[i]
            position[i] = 1.0
            entry_shares = int(capital_unit // entry_price) if entry_price else 0
            trades.append({
                "date": series[i].get("date", ""),
                "code": code,
                "name": name,
                "action": "buy",
                "price": round(closes[i], 2),
                "shares": entry_shares,
                "amount": round(entry_shares * closes[i], 2),
            })
        elif holding:
            peak = max(peak, closes[i])
            if exit_event:
                holding = False
                position[i] = 0.0
                pnl = (closes[i] - entry_price) * entry_shares
                trades.append({
                    "date": series[i].get("date", ""),
                    "code": code,
                    "name": name,
                    "action": "sell",
                    "price": round(closes[i], 2),
                    "shares": entry_shares,
                    "amount": round(entry_shares * closes[i], 2),
                    "pnl": round(pnl, 2),
                })
                entry_price = 0.0
                entry_i = 0
                peak = 0.0
                entry_shares = 0
            else:
                position[i] = 1.0
        else:
            position[i] = 0.0

        # 该标的对组合日收益的贡献（含第 0 日为 0）
        daily_ret = closes[i] / closes[i - 1] - 1.0 if closes[i - 1] else 0.0
        contrib[i] = position[i] * daily_ret * weight

    return {"position": position, "contrib": contrib, "trades": trades}


# ---------------------------------------------------------------------------
# 组合层：多标的等权事件驱动回测
# ---------------------------------------------------------------------------
def run_event_backtest(
    rules: List[dict],
    universe: List[str],
    startDate: str,
    endDate: str,
    initialCapital: float,
    risk: Optional[dict] = None,
    strategyName: str = "",
    series_map: Optional[dict] = None,
    names_map: Optional[dict] = None,
) -> dict:
    """运行事件驱动回测（多标的等权组合）。

    参数：
        rules:       事件规则列表，每条 ``{"side":"entry"/"exit","kind":...,"params":{...}}``
        universe:    标的代码列表（如 ["sh600519","sz000858"]）
        startDate/endDate: 回测区间（YYYY-MM-DD；空=取足够长历史）
        initialCapital: 初始资金（元）
        risk:         全局风控 ``{"stopLoss":8.0,"takeProfit":20.0}``（可选）
        strategyName: 策略展示名（可选）
        series_map:   测试注入用——{code: [{"date","close",...}]}；生产环境由服务层注入真实 K线
        names_map:    测试/生产注入的 {code: 名称}

    返回：与 ``run_backtest`` 同构的 result 字典，额外含 ``mode="event"`` 与 ``universe``。
    """
    risk = risk or {}
    entry_rules = [r for r in rules if r.get("side", "entry") == "entry"]
    exit_rules = [r for r in rules if r.get("side") == "exit"]
    if not entry_rules:
        # 兜底：至少给一条金叉入场，避免空规则无交易
        entry_rules = [{"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}}]

    # 规整 universe
    codes = [c for c in (universe or []) if c]
    if not codes and series_map:
        codes = list(series_map.keys())
    if not codes:
        raise RuntimeError("事件驱动回测需要至少一个标的（universe 非空）")

    # 准备每个标的的序列（截断到最短，按「交易日索引」对齐）
    prepared = []
    for code in codes:
        ser = (series_map or {}).get(code)
        if not ser:
            continue
        # 按区间过滤
        if startDate:
            ser = [k for k in ser if k.get("date", "") >= startDate]
        if endDate:
            ser = [k for k in ser if k.get("date", "") <= endDate]
        if len(ser) < 30:
            # 区间过窄时放宽到全部可用数据
            ser = (series_map or {}).get(code) or []
        if len(ser) < 25:
            continue
        prepared.append((code, ser))

    if not prepared:
        raise RuntimeError("所有标的 K线 数据不足，无法回测")

    # 截断到最短序列长度，保证每个标的每天都有数据（等权分母恒定）
    min_n = min(len(ser) for _, ser in prepared)
    # 取每个标的「末尾 min_n 根」，使日期窗口对齐到近期重叠段
    aligned = []
    for code, ser in prepared:
        tail = ser[-min_n:]
        aligned.append((code, tail))
    n = min_n

    S = len(aligned)               # 有效标的数（等权分母）
    weight = 1.0 / S if S else 1.0
    capital_unit = initialCapital * weight

    # 逐标的回测（并行加速，#P2）
    from concurrent.futures import ThreadPoolExecutor, as_completed
    all_contrib = [0.0] * n
    all_trades: List[dict] = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(_backtest_single, code, name, ser, entry_rules, exit_rules, risk, weight, capital_unit): code
            for code, ser in aligned
            for name in [(names_map or {}).get(code, code)]
        }
        for f in as_completed(futures):
            res = f.result()
            for i in range(n):
                all_contrib[i] += res["contrib"][i]
            all_trades.extend(res["trades"])

    # 组合权益曲线（与 M8 口径一致：equity[0]=初始资金，其后逐日复利）
    equity = [initialCapital]
    for i in range(1, n):
        r = all_contrib[i]
        equity.append(equity[-1] * (1.0 + r))

    # 指标
    port_rets = all_contrib[1:]  # 第 0 日为基准，无收益
    total_return = equity[-1] / equity[0] - 1.0 if equity[0] else 0.0
    n_days = len(port_rets)
    years = n_days / 252.0 if n_days else 1.0
    annualized = (1 + total_return) ** (1 / years) - 1 if (years > 0 and total_return > -1) else 0.0
    mean_r = sum(port_rets) / n_days if n_days else 0.0
    std_r = _safe_std(port_rets)
    sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else 0.0

    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)

    # 成交回合统计（按 code+相邻 buy/sell 配对，持仓天数用真实日期差）
    round_trips = 0
    wins = 0
    hold_days_total = 0
    pending_buy = {}
    for t in all_trades:
        if t["action"] == "buy":
            pending_buy.setdefault(t["code"], []).append(t)
        else:
            buys = pending_buy.get(t["code"], [])
            if buys:
                b = buys.pop(0)
                round_trips += 1
                if t["price"] > b["price"]:
                    wins += 1
                # 真实持仓自然日（按日期字符串差；解析失败则记 1）
                try:
                    from datetime import datetime as _dt

                    d0 = _dt.strptime(b["date"], "%Y-%m-%d")
                    d1 = _dt.strptime(t["date"], "%Y-%m-%d")
                    hold_days_total += max(1, (d1 - d0).days)
                except Exception:
                    hold_days_total += 1
    win_rate = (wins / round_trips * 100) if round_trips else 0.0
    avg_hold = (hold_days_total / round_trips) if round_trips else 0.0

    label = strategyName or "事件驱动组合"
    return {
        "mode": "event",
        "strategyName": label,
        "symbol": f"{S}只标的等权",
        "universe": codes,
        "startDate": aligned[0][1][0].get("date", "") if aligned else "",
        "endDate": aligned[0][1][-1].get("date", "") if aligned else "",
        "totalReturn": round(total_return * 100, 2),
        "annualizedReturn": round(annualized * 100, 2),
        "sharpeRatio": round(sharpe, 2),
        "maxDrawdown": round(max_dd * 100, 2),
        "winRate": round(win_rate, 1),
        "totalTrades": len(all_trades),
        "avgHoldDays": round(avg_hold, 1),
        "equityCurve": [{"date": aligned[0][1][i].get("date", ""), "value": round(equity[i], 2)} for i in range(n)],
        "trades": all_trades,
        "dataSource": "event-engine",
    }
