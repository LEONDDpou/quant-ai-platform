"""因子分析服务 — 移植自 hugo2046/QuantsPlaybook 的因子研究与评价体系。

与原始仓库的对应关系：
- 因子定义复刻其「因子 Notebook」系列：动量(momentum)、反转(reversal)、
  特质波动率(idiosyncratic volatility)、均线收敛发散(MA convergence/divergence)。
- 因子评价复刻其 performance.py 的核心指标：信息系数 IC（Spearman 秩相关）、
  ICIR（滚动 IC 的均值/标准差）、分组收益（按因子值分 5 组，多空 = Q5 - Q1）。
  原始仓库用 statsmodels 做 t 检验；本服务改用 scipy.stats.spearmanr，避免引入
  qlib / lightgbm / xgboost / tushare / wind 等重依赖与环境锁定（见项目 QuantsPlaybook 集成说明）。

防未来函数（Iron rule）：
- 因子值在第 t 日收盘后计算，仅使用 t 日及之前的数据（close[0..t]）。
- 预测目标为未来 horizon 日收益率 r_{t->t+h} = close[t+h]/close[t] - 1，
  因子与目标均不含任何未来信息。

免责声明：本模块为模型驱动的量化研究工具，结果不构成任何投资建议。
"""
from __future__ import annotations

import time
import concurrent.futures as _cf
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

from app.services import westock_client as ws

# 拉取的日 K 线长度（约 4 年，保证 250 日 warmup 后有足够样本）
KLINE_LIMIT = 1000
# 特质波动率所需的市值基准（沪深300 指数）
MARKET_INDEX = "sh000300"

# 因子中文名映射（前端展示用）
FACTOR_LABELS = {
    "momentum": "动量因子",
    "reversal": "反转因子",
    "idio_vol": "特质波动率因子",
    "ma_conv": "均线收敛发散因子",
    "composite": "多因子复合",
}


# ============================================================
# 代码归一化 + 数据获取
# ============================================================
def normalize_symbol(code: str) -> str:
    """接受 600519 / 600519.SH / sh600519 等写法，返回 westock 形如 sh600519 的符号。"""
    c = (code or "").strip().lower()
    if not c:
        return ""
    if c[:2] in ("sh", "sz", "bj"):
        return c
    if "." in c:
        num, _, suffix = c.partition(".")
        suffix = suffix.upper()
        prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(suffix, "")
        if prefix:
            return f"{prefix}{num}"
    if c.isdigit():
        if c.startswith(("6", "688")):
            return f"sh{c}"
        if c.startswith(("0", "3")):
            return f"sz{c}"
        if c.startswith(("8", "4")):
            return f"bj{c}"
    return c


def _fetch_kline(sym: str, limit: int = KLINE_LIMIT) -> pd.DataFrame:
    """通过 westock 拉取真实日 K 线，返回按日期升序的 OHLCV DataFrame。"""
    rows = ws.run_table(
        ["kline", sym, "--period", "day", "--limit", str(limit), "--fq", "qfq"],
        timeout=30,
    )
    if not rows:
        raise RuntimeError(f"westock 未返回 {sym} 的 K 线数据")
    df = pd.DataFrame(rows)
    df = df.rename(columns={"last": "close"})
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ============================================================
# 因子计算（严格防未来函数：第 t 日因子仅用 close[0..t]）
# ============================================================
def _ma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()


def _factor_series(close: pd.Series, market_ret: Optional[pd.Series],
                   factor: str, n_mom: int = 20, skip: int = 1) -> pd.Series:
    """返回与 close 对齐的因子序列（前若干行为 NaN）。"""
    arr = close.to_numpy(dtype=float)
    m = len(arr)
    out = np.full(m, np.nan, dtype=float)

    if factor == "momentum":
        # 过去 n_mom 日收益率（跳过最近 skip 日，避免微结构噪声）
        for i in range(m):
            if i - skip - n_mom >= 0:
                base = arr[i - skip - n_mom]
                if base:
                    out[i] = arr[i - skip] / base - 1.0

    elif factor == "reversal":
        # 短期反转：近 5 日收益率（取反，原值越大代表近期跌得多、未来更易反弹）
        k = 5
        for i in range(m):
            if i - skip - k >= 0:
                base = arr[i - skip - k]
                if base:
                    out[i] = arr[i - skip] / base - 1.0  # 原始 5 日收益，评价时取负向

    elif factor == "ma_conv":
        # 均线收敛发散：(MA5 - MA60) / MA60，正值=发散(短在上)，近0=收敛
        ma5 = _ma(close, 5)
        ma60 = _ma(close, 60)
        for i in range(m):
            if pd.notna(ma5.iloc[i]) and pd.notna(ma60.iloc[i]) and ma60.iloc[i]:
                out[i] = (ma5.iloc[i] - ma60.iloc[i]) / ma60.iloc[i]

    elif factor == "idio_vol":
        # 特质波动率：个股收益对市值基准（沪深300）做 CAPM 回归后的残差波动（年化）
        if market_ret is None or len(market_ret) != m:
            # 无基准时退化为对 MA20 趋势的偏离波动（仅作兜底）
            trend = _ma(close, 20).pct_change().fillna(0.0)
            stock_ret = close.pct_change().fillna(0.0)
            resid = (stock_ret - trend).rolling(60, min_periods=60)
            out = (resid.std() * np.sqrt(252)).to_numpy(dtype=float)
            return pd.Series(out, index=close.index)
        stock_ret = close.pct_change().fillna(0.0).to_numpy(dtype=float)
        mkt = market_ret.to_numpy(dtype=float)
        win = 60
        for i in range(m):
            if i - win + 1 < 0:
                continue
            y = stock_ret[i - win + 1 : i + 1]
            x = mkt[i - win + 1 : i + 1]
            if len(y) < win:
                continue
            mask = np.isfinite(y) & np.isfinite(x)
            if mask.sum() < 30:
                continue
            try:
                b1, b0 = np.polyfit(x[mask], y[mask], 1)
                resid = y[mask] - (b0 + b1 * x[mask])
                out[i] = float(np.std(resid, ddof=1) * np.sqrt(252))
            except Exception:
                out[i] = np.nan

    return pd.Series(out, index=close.index)


# ============================================================
# 因子评价（IC / ICIR / 分组收益）
# ============================================================
def _rolling_ic(factor: pd.Series, fwd: pd.Series, window: int = 60) -> list[float]:
    """逐窗口 Spearman IC（仅保留样本数 >= 20 的窗口）。"""
    out: list[float] = []
    idx = factor.dropna().index
    vals_f = factor.loc[idx].to_numpy(float)
    vals_r = fwd.loc[idx].to_numpy(float)
    for s in range(0, len(vals_f) - window + 1):
        f_seg = vals_f[s : s + window]
        r_seg = vals_r[s : s + window]
        if np.isfinite(f_seg).sum() < 20:
            continue
        ic, _ = stats.spearmanr(f_seg, r_seg)
        if np.isfinite(ic):
            out.append(float(ic))
    return out


def _group_returns(factor: pd.Series, fwd: pd.Series, q: int = 5) -> list[dict]:
    """按因子值分位分组，计算各组平均未来收益（多空 = Q_last - Q_first）。"""
    df = pd.DataFrame({"f": factor, "r": fwd}).dropna()
    if len(df) < q * 5:
        return []
    try:
        df["grp"] = pd.qcut(df["f"].rank(method="first"), q, labels=False) + 1
    except Exception:
        return []
    groups = []
    for g in range(1, q + 1):
        sub = df[df["grp"] == g]
        if len(sub) == 0:
            continue
        groups.append({
            "group": g,
            "avgFactor": round(float(sub["f"].mean()), 5),
            "avgForwardReturn": round(float(sub["r"].mean() * 100), 3),  # 转为百分比
            "count": int(len(sub)),
        })
    return groups


@dataclass
class FactorResult:
    code: str
    symbol: str
    factor: str
    factorLabel: str
    horizon: int
    ic: float = 0.0                 # 全样本 Spearman IC
    icir: float = 0.0               # 滚动 IC 均值 / 标准差
    icWinRate: float = 0.0          # 滚动 IC > 0 的比例
    longShortReturn: float = 0.0    # Q5 - Q1 平均未来收益（百分点）
    groups: list[dict] = field(default_factory=list)
    latestFactor: float = 0.0       # 最新因子值
    latestSignal: str = ""          # 最新信号描述
    nSamples: int = 0
    startDate: str = ""
    endDate: str = ""
    note: str = ""


_CACHE: dict[str, tuple[float, FactorResult]] = {}
_CACHE_TTL = 300.0


def analyze(code: str, factor: str = "momentum", horizon: int = 20) -> FactorResult:
    """端到端：取数 -> 因子序列 -> 未来收益 -> IC/ICIR/分组收益。结果缓存 5 分钟。"""
    # 复合因子本质是横截面概念，单标的 analyze 不支持，回退到动量
    if factor not in FACTOR_LABELS or factor == "composite":
        factor = "momentum"
    sym = normalize_symbol(code)
    cache_key = f"{sym}#{factor}#{horizon}"
    now = time.time()
    if cache_key in _CACHE and now - _CACHE[cache_key][0] < _CACHE_TTL:
        return _CACHE[cache_key][1]

    try:
        df = _fetch_kline(sym)
    except Exception as e:  # noqa: BLE001
        res = FactorResult(code=code, symbol=sym, factor=factor,
                           factorLabel=FACTOR_LABELS[factor], horizon=horizon,
                           note=f"行情获取失败：{type(e).__name__} {e}")
        return res

    # 市值基准（特质波动率需要）；失败则进入兜底分支
    market_ret: Optional[pd.Series] = None
    if factor == "idio_vol":
        try:
            mdf = _fetch_kline(MARKET_INDEX, limit=KLINE_LIMIT)
            # 按日期对齐到个股交易日
            mret = mdf.set_index("date")["close"].pct_change().fillna(0.0)
            mret = mret.reindex(df["date"]).fillna(0.0)
            market_ret = mret.reset_index(drop=True)
            if len(market_ret) != len(df):
                market_ret = None
        except Exception:
            market_ret = None

    close = df["close"]
    factor_series = _factor_series(close, market_ret, factor)

    # 未来 horizon 日收益率（不含未来信息：base 用 close[t]）
    fwd_ret = close.shift(-horizon) / close - 1.0

    pair = pd.DataFrame({"f": factor_series, "r": fwd_ret}).dropna()
    if len(pair) < 60:
        res = FactorResult(code=code, symbol=sym, factor=factor,
                           factorLabel=FACTOR_LABELS[factor], horizon=horizon,
                           startDate=df["date"].iloc[0].strftime("%Y-%m-%d"),
                           endDate=df["date"].iloc[-1].strftime("%Y-%m-%d"),
                           nSamples=len(pair),
                           note="历史样本不足（需 >= 60 个完整窗口），无法稳定评价。")
        return res

    # 全样本 IC
    ic, _ = stats.spearmanr(pair["f"], pair["r"])

    # 滚动 IC / ICIR / 胜率
    rolling = _rolling_ic(pair["f"], pair["r"], window=60)
    icir = 0.0
    ic_win = 0.0
    if len(rolling) >= 3:
        arr = np.array(rolling, dtype=float)
        sd = arr.std(ddof=1)
        icir = float(arr.mean() / sd) if sd > 0 else 0.0
        ic_win = float((arr > 0).mean() * 100)

    # 分组收益
    groups = _group_returns(pair["f"], pair["r"], q=5)
    long_short = 0.0
    if len(groups) >= 2:
        long_short = float(groups[-1]["avgForwardReturn"] - groups[0]["avgForwardReturn"])

    # 最新信号
    latest = float(pair["f"].iloc[-1])
    # 反转因子取负向：因子值越负（近期跌越多）未来越可能反弹
    if factor == "reversal":
        signal = "近期超跌，关注反弹" if latest < 0 else "近期强势，警惕回落"
    elif factor == "idio_vol":
        signal = f"特质波动率高（{latest*100:.1f}%），个股特异风险大" if latest > 0.3 else "特质波动率温和"
    elif factor == "momentum":
        signal = "动量为正，趋势延续" if latest > 0 else "动量为负，趋势走弱"
    else:  # ma_conv
        signal = "均线发散（短线上穿），多头排列" if latest > 0 else "均线收敛，方向待选"
    # IC 方向修正信号（若 IC 与直觉相反，提示无效）
    if abs(ic) < 0.01:
        signal += "（但全样本 IC≈0，因子在该区间预测力弱）"

    res = FactorResult(
        code=code, symbol=sym, factor=factor, factorLabel=FACTOR_LABELS[factor],
        horizon=horizon,
        ic=round(float(ic), 4),
        icir=round(icir, 4),
        icWinRate=round(ic_win, 1),
        longShortReturn=round(long_short, 3),
        groups=groups,
        latestFactor=round(latest, 5),
        latestSignal=signal,
        nSamples=len(pair),
        startDate=df["date"].iloc[0].strftime("%Y-%m-%d"),
        endDate=df["date"].iloc[-1].strftime("%Y-%m-%d"),
        note="基于 westock 真实日K线 + QuantsPlaybook 风格因子定义，用 scipy Spearman 计算 IC/ICIR 与分组多空收益（未引入 qlib/statsmodels 等重依赖）。",
    )
    _CACHE[cache_key] = (now, res)
    return res


# ============================================================
# 横截面因子研究（多股票 × 单因子，对标 QuantsPlaybook 的跨截面 IC 评价）
# ============================================================
# 单标的 K 线缓存（横截面需拉一篮子，避免重复打接口）
_KLINE_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}
_KLINE_CACHE_TTL = 600.0

# 横截面结果缓存（整篮子计算较重）
_CS_CACHE: dict[str, tuple[float, "CrossSectionResult"]] = {}
_CS_CACHE_TTL = 600.0

# 横截面 IC 计算所需的最小截面宽度（某日有效股票数低于此值则跳过）
_MIN_CROSS_SECTION = 20
# 横截面拉取的 K 线长度（约 2.4 年，足够 60 日 warmup + 预测窗口 + 抽样）
_CS_KLINE_LIMIT = 600


@dataclass
class CrossSectionResult:
    factor: str
    factorLabel: str
    index: str
    horizon: int
    sampleSize: int
    nStocks: int
    nDates: int
    icMean: float = 0.0
    icStd: float = 0.0
    icir: float = 0.0
    icWinRate: float = 0.0
    longShortReturn: float = 0.0
    icSeries: list[dict] = field(default_factory=list)   # [{date, ic, coverage}]
    groups: list[dict] = field(default_factory=list)      # [{group, avgForwardReturn, count}]
    startDate: str = ""
    endDate: str = ""
    note: str = ""


def _get_kline_cached(sym: str, limit: int = _CS_KLINE_LIMIT) -> pd.DataFrame:
    """带缓存的 K 线获取；过滤掉 close<=0（如当日未完成 bar）。"""
    now = time.time()
    if sym in _KLINE_CACHE and now - _KLINE_CACHE[sym][0] < _KLINE_CACHE_TTL:
        return _KLINE_CACHE[sym][1]
    df = _fetch_kline(sym, limit=limit)
    df = df[df["close"] > 0].reset_index(drop=True)
    _KLINE_CACHE[sym] = (now, df)
    return df


def cross_sectional_analyze(
    index: str = "sh000300",
    factor: str = "momentum",
    horizon: int = 20,
    sample_size: int = 50,
) -> CrossSectionResult:
    """多股票横截面因子研究（移植 QuantsPlaybook 的跨截面 IC 评价思路）。

    流程：
    1. 拉取指数成份股（如沪深300），按步长抽样 sample_size 只，确保覆盖指数不同区段；
    2. 并行拉取每只样本股的日 K 线，本地计算因子序列与未来 horizon 日收益率；
    3. 对每个交易日，跨截面计算因子值 vs 未来收益的 Spearman IC（截面宽度 >= 20 才计入）；
    4. 汇总 IC 均值 / ICIR（IC 序列均值/标准差）/ IC 胜率，并 pooling 所有 (因子, 收益) 对
       做五分组，多空 = Q5 - Q1。

    防未来函数（Iron rule）：
    - 因子值在第 t 日收盘后计算，仅用 t 日及之前数据；
    - 预测目标为未来 horizon 日收益，因子与目标均不含未来信息；
    - 横截面 IC 在「同一交易日」内对股票横截面计算，不跨时间泄漏。
    """
    if factor not in FACTOR_LABELS:
        factor = "momentum"
    idx_sym = normalize_symbol(index) or "sh000300"

    cache_key = f"{idx_sym}#{factor}#{horizon}#{sample_size}"
    now = time.time()
    if cache_key in _CS_CACHE and now - _CS_CACHE[cache_key][0] < _CS_CACHE_TTL:
        return _CS_CACHE[cache_key][1]

    # 1) 指数成份股
    try:
        comp_rows = ws.run_table(["index", idx_sym], timeout=30)
    except Exception as e:  # noqa: BLE001
        return CrossSectionResult(
            factor=factor, factorLabel=FACTOR_LABELS[factor], index=idx_sym,
            horizon=horizon, sampleSize=sample_size, nStocks=0, nDates=0,
            note=f"指数成份股获取失败：{type(e).__name__} {e}",
        )
    codes = sorted({r["code"] for r in comp_rows if r.get("code")})
    if not codes:
        return CrossSectionResult(
            factor=factor, factorLabel=FACTOR_LABELS[factor], index=idx_sym,
            horizon=horizon, sampleSize=sample_size, nStocks=0, nDates=0,
            note="指数成份股为空，无法构建横截面样本。",
        )

    # 步长抽样，覆盖指数不同区段（确定性，便于复现）
    n_total = len(codes)
    if n_total > sample_size:
        step = n_total / sample_size
        sampled = [codes[int(i * step)] for i in range(sample_size)]
    else:
        sampled = codes
    sampled = sampled[:sample_size]

    # 2) 并行拉 K 线 + 计算因子/未来收益
    # 特质波动率 / 复合因子 需要市值基准（沪深300）收益序列
    market_ret: Optional[pd.Series] = None
    if factor == "idio_vol" or factor == "composite":
        try:
            mdf = _get_kline_cached(MARKET_INDEX, limit=_CS_KLINE_LIMIT)
            market_ret = mdf.set_index("date")["close"].pct_change().fillna(0.0)
        except Exception:
            market_ret = None

    stock_data: dict[str, dict] = {}

    def _work(sym: str) -> tuple[str, Optional[dict]]:
        try:
            df = _get_kline_cached(sym, limit=_CS_KLINE_LIMIT)
        except Exception:
            return sym, None
        if len(df) < 60 + horizon:
            return sym, None
        close = df["close"]
        mr: Optional[pd.Series] = None
        if market_ret is not None:
            mr = market_ret.reindex(df["date"]).fillna(0.0).reset_index(drop=True)
            if len(mr) != len(close):
                mr = None
        fwd = close.shift(-horizon) / close - 1.0
        dates = df["date"].dt.strftime("%Y-%m-%d").tolist()
        if factor == "composite":
            # 复合因子：同时计算 4 个成分因子，横截面内再 z-score 复合
            comp: dict[str, np.ndarray] = {}
            for k in ("momentum", "reversal", "idio_vol", "ma_conv"):
                fs = _factor_series(close, mr, k)
                comp[k] = fs.to_numpy(dtype=float)
            return sym, {
                "dates": dates,
                "comp": comp,
                "fwd": fwd.to_numpy(dtype=float),
            }
        fs = _factor_series(close, mr, factor)
        return sym, {
            "dates": dates,
            "f": fs.to_numpy(dtype=float),
            "r": fwd.to_numpy(dtype=float),
        }

    with _cf.ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(_work, s): s for s in sampled}
        for fut in _cf.as_completed(futs):
            sym, res = fut.result()
            if res is not None:
                stock_data[sym] = res

    if len(stock_data) < _MIN_CROSS_SECTION:
        return CrossSectionResult(
            factor=factor, factorLabel=FACTOR_LABELS[factor], index=idx_sym,
            horizon=horizon, sampleSize=sample_size, nStocks=len(stock_data), nDates=0,
            note=f"有效样本股票仅 {len(stock_data)} 只（需 >= {_MIN_CROSS_SECTION}），无法稳定计算横截面 IC。",
        )

    # 3) 逐交易日横截面 IC
    ic_series: list[dict] = []
    pooled_f: list[float] = []
    pooled_r: list[float] = []

    if factor == "composite":
        # ===== 多因子复合：横截面内 z-score 标准化 + 经济先验定向 + 等权求和 =====
        # 成分因子定向（higher composite = higher expected forward return）：
        #   动量(+1) 发散(+1) 取正向；反转(-1) 低波动溢价(-1) 取负向。
        _COMP_KEYS = ("momentum", "reversal", "idio_vol", "ma_conv")
        _ORIENT = {"momentum": 1.0, "reversal": -1.0, "idio_vol": -1.0, "ma_conv": 1.0}
        _by_date_comp: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: {k: [] for k in _COMP_KEYS})
        _by_date_fwd: dict[str, list[float]] = defaultdict(list)
        for d in stock_data.values():
            comp = d.get("comp")
            if comp is None:
                continue
            for j in range(len(d["dates"])):
                fwdv = d["fwd"][j]
                if not np.isfinite(fwdv):
                    continue
                if not all(np.isfinite(comp[k][j]) for k in _COMP_KEYS):
                    continue
                _by_date_fwd[d["dates"][j]].append(float(fwdv))
                for k in _COMP_KEYS:
                    _by_date_comp[d["dates"][j]][k].append(float(comp[k][j]))

        for date in sorted(_by_date_comp.keys()):
            n_c = len(_by_date_comp[date]["momentum"])
            if n_c < _MIN_CROSS_SECTION:
                continue
            scores = np.zeros(n_c, dtype=float)
            for k in _COMP_KEYS:
                arr = np.array(_by_date_comp[date][k], dtype=float)
                mu, sd = arr.mean(), arr.std(ddof=1)
                z = (arr - mu) / sd if sd > 0 else np.zeros(n_c)
                scores += _ORIENT[k] * z
            fwd_arr = np.array(_by_date_fwd[date], dtype=float)
            ic, _ = stats.spearmanr(scores, fwd_arr)
            if np.isfinite(ic):
                ic_series.append({"date": date, "ic": round(float(ic), 4), "coverage": n_c})
                for s, r in zip(scores, fwd_arr):
                    pooled_f.append(float(s))
                    pooled_r.append(float(r))
    else:
        by_date: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for d in stock_data.values():
            for j in range(len(d["dates"])):
                fv, rv = d["f"][j], d["r"][j]
                if np.isfinite(fv) and np.isfinite(rv):
                    by_date[d["dates"][j]].append((float(fv), float(rv)))
        for date in sorted(by_date.keys()):
            pairs = by_date[date]
            if len(pairs) < _MIN_CROSS_SECTION:
                continue
            fv = np.array([p[0] for p in pairs], dtype=float)
            rv = np.array([p[1] for p in pairs], dtype=float)
            ic, _ = stats.spearmanr(fv, rv)
            if np.isfinite(ic):
                ic_series.append({"date": date, "ic": round(float(ic), 4), "coverage": len(pairs)})
        for pairs in by_date.values():
            for fv, rv in pairs:
                pooled_f.append(fv)
                pooled_r.append(rv)

    # 4) 汇总
    ic_mean = ic_std = icir = ic_win = 0.0
    if ic_series:
        ics = np.array([x["ic"] for x in ic_series], dtype=float)
        ic_mean = float(ics.mean())
        ic_std = float(ics.std(ddof=1)) if len(ics) > 1 else 0.0
        icir = float(ic_mean / ic_std) if ic_std > 0 else 0.0
        ic_win = float((ics > 0).mean() * 100)

    # 五分组（pooling 全部 (因子/复合分, 收益) 对）
    groups: list[dict] = []
    long_short = 0.0
    if pooled_f:
        allf = np.array(pooled_f, dtype=float)
        allr = np.array(pooled_r, dtype=float)
        dfp = pd.DataFrame({"f": allf, "r": allr})
        try:
            dfp["grp"] = pd.qcut(dfp["f"].rank(method="first"), 5, labels=False) + 1
            for g in range(1, 6):
                sub = dfp[dfp["grp"] == g]
                if len(sub) == 0:
                    continue
                groups.append({
                    "group": g,
                    "avgForwardReturn": round(float(sub["r"].mean() * 100), 3),
                    "count": int(len(sub)),
                })
            if len(groups) >= 2:
                long_short = float(groups[-1]["avgForwardReturn"] - groups[0]["avgForwardReturn"])
        except Exception:
            groups = []

    all_dates = sorted(by_date.keys()) if factor != "composite" else sorted(
        {dt for d in stock_data.values() for dt in d["dates"]})
    _cs_note = (
        "多因子复合：对动量/反转/特质波动/均线收敛 4 个因子做横截面 z-score 标准化，"
        "按经济先验定向（动量、发散取正；反转、低波动溢价取负）后等权求和，再评价跨截面 IC。"
        "未引入 qlib/statsmodels 等重依赖，样本为沪深300成份股步长抽样。"
    ) if factor == "composite" else (
        "基于 westock 真实日K线 + QuantsPlaybook 风格因子定义，做横截面 IC/ICIR 与五分组多空评价"
        "（未引入 qlib/statsmodels 等重依赖）。样本为指数成份股步长抽样。"
    )
    res = CrossSectionResult(
        factor=factor, factorLabel=FACTOR_LABELS[factor], index=idx_sym,
        horizon=horizon, sampleSize=sample_size,
        nStocks=len(stock_data), nDates=len(ic_series),
        icMean=round(ic_mean, 4), icStd=round(ic_std, 4), icir=round(icir, 4),
        icWinRate=round(ic_win, 1), longShortReturn=round(long_short, 3),
        icSeries=ic_series, groups=groups,
        startDate=all_dates[0] if all_dates else "",
        endDate=all_dates[-1] if all_dates else "",
        note=_cs_note,
    )
    _CS_CACHE[cache_key] = (now, res)
    return res


def clear_cache() -> None:
    _CACHE.clear()
    _CS_CACHE.clear()
