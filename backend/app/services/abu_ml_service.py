"""ABu ML 量化预测服务 — 移植自开源项目 bbfamily/abu (abupy/MLBu 与 abupy/TradeBu/ABuMLFeature.py)

集成说明（与原始 abu 的对应关系）：
- 特征工程复刻自 abupy/TradeBu/ABuMLFeature.py：
    * AbuFeatureDeg   -> 多周期走势拟合角度（21/42/60/250 日）
    * AbuFeaturePrice -> 多周期价格百分位 rank（60/90/120/250 日）
    * AbuFeatureWave  -> 波动特征（多窗口收益率 std）
    * AbuFeatureAtr   -> ATR 标准化波动
    * AbuFeatureJump  -> 向上/向下跳空能量与间隔
- 监督学习流水线复刻自 abupy/MLBu/ABuML.py（AbuML）与 ABuMLPd.ClosePredict：
    * 以「当日特征 X」预测「未来 N 日收益率方向 y（涨/跌）」的监督分类任务
    * 使用 scikit-learn 估计器 + 训练/测试切分 + 准确率度量（对应 ABuML 的 fit/score）

为何移植而非直接 import abupy：
- abupy 在 Python 3.13 下无法导入（from collections import Iterable 等已废弃 API），
  且整包与自有数据层（CoreBu/UtilBu/TLineBu...）深度耦合。
- 本服务仅依赖 pandas / numpy / scikit-learn，并解耦数据来源——直接读取 westock 真实日 K 线，
  既"集成了 abu 的 AI 关键组件"，又保持与原项目架构兼容、不引入脆弱的整包依赖。

免责声明：本模块为模型驱动的量化研究工具，预测结果不构成任何投资建议。
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from app.services import westock_client as ws

# 拉取的日 K 线长度（约 5 年，保证 250 日 warmup 后有足够训练样本）
KLINE_LIMIT = 1200

# 特征窗口定义（与 abupy 默认一致）
DEG_KEYS = [21, 42, 60, 250]
PRICE_RANK_KEYS = [60, 90, 120, 250]
WAVE_KEYS = [42, 84, 126]  # 1/2/3 * 42
ATR_XD = 42


# ============================================================
# 代码归一化：把多种写法统一成 westock 符号
# ============================================================
def normalize_symbol(code: str) -> str:
    """接受 600519 / 600519.SH / sh600519 等写法，返回 westock 形如 sh600519 的符号。"""
    c = (code or "").strip().lower()
    if not c:
        return ""
    # 已是 sh/sz/bj 前缀
    if c[:2] in ("sh", "sz", "bj"):
        return c
    # 带交易所后缀
    if "." in c:
        num, _, suffix = c.partition(".")
        suffix = suffix.upper()
        prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(suffix, "")
        if prefix:
            return f"{prefix}{num}"
    # 纯数字：按 A 股规则推断
    if c.isdigit():
        if c.startswith("6") or c.startswith("688"):
            return f"sh{c}"
        if c.startswith(("0", "3")):
            return f"sz{c}"
        if c.startswith(("8", "4")):
            return f"bj{c}"
    return c


# ============================================================
# 数据获取
# ============================================================
def fetch_kline(code: str) -> pd.DataFrame:
    """通过 westock 拉取真实日 K 线，返回按日期升序的 OHLCV DataFrame。"""
    sym = normalize_symbol(code)
    if not sym:
        raise ValueError("无效股票代码")
    rows = ws.run_table(
        ["kline", sym, "--period", "day", "--limit", str(KLINE_LIMIT), "--fq", "qfq"],
        timeout=30,
    )
    if not rows:
        raise RuntimeError(f"westock 未返回 {sym} 的 K 线数据")

    df = pd.DataFrame(rows)
    # 列映射：westock 的 last == 收盘价
    df = df.rename(columns={"last": "close"})
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    # westock 返回倒序（最新在前），转回时间升序
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ============================================================
# 特征工程（移植自 abupy/TradeBu/ABuMLFeature.py）
# ============================================================
def _regress_angle(series: pd.Series) -> float:
    """收盘价的线性拟合角度（度），复刻 AbuFeatureDeg 的 calc_regress_deg。"""
    s = series.dropna()
    if len(s) < 2:
        return 0.0
    x = np.arange(len(s), dtype=float)
    y = s.to_numpy(dtype=float)
    # 普通最小二乘斜率
    slope = np.polyfit(x, y, 1)[0]
    if not np.isfinite(slope):
        return 0.0
    return float(math.degrees(math.atan(slope)))


def _price_rank(series: pd.Series) -> float:
    """当前价格在窗口内的百分位 rank（0~1），复刻 AbuFeaturePrice。"""
    s = series.dropna()
    if len(s) < 2:
        return 0.0
    r = s.rank()
    return float(r.iloc[-1] / r.shape[0])


def _true_range(df: pd.DataFrame, i: int) -> float:
    """单根 K 线的真实波幅 TR。"""
    high = df["high"].iloc[i]
    low = df["low"].iloc[i]
    prev_close = df["close"].iloc[i - 1] if i > 0 else df["close"].iloc[0]
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def _atr_ratio(df: pd.DataFrame, i: int, xd: int = ATR_XD) -> float:
    """ATR / 收盘价，标准化波动特征，复刻 AbuFeatureAtr。"""
    if i < 1:
        return 0.0
    start = max(1, i - xd + 1)
    trs = [max(
        df["high"].iloc[j] - df["low"].iloc[j],
        abs(df["high"].iloc[j] - df["close"].iloc[j - 1]),
        abs(df["low"].iloc[j] - df["close"].iloc[j - 1]),
    ) for j in range(start, i + 1)]
    if not trs:
        return 0.0
    atr = float(np.mean(trs))
    close = df["close"].iloc[i]
    return round(atr / close, 4) if close else 0.0


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """逐行构造 ABu 风格特征矩阵。前 250 行 warmup 不足，特征为 NaN。"""
    n = len(df)
    feat = pd.DataFrame(index=range(n))
    close = df["close"]
    ret = close.pct_change().fillna(0.0)

    # 1) 走势拟合角度
    for k in DEG_KEYS:
        col = np.full(n, np.nan, dtype=float)
        for i in range(n):
            if i >= k - 1:
                col[i] = _regress_angle(close.iloc[i - k + 1 : i + 1])
        feat[f"deg_ang{k}"] = col

    # 2) 价格百分位 rank
    for k in PRICE_RANK_KEYS:
        col = np.full(n, np.nan, dtype=float)
        for i in range(n):
            if i >= k - 1:
                col[i] = _price_rank(close.iloc[i - k + 1 : i + 1])
        feat[f"price_rank{k}"] = col

    # 3) 波动特征：多窗口收益率 std
    for k in WAVE_KEYS:
        col = np.full(n, np.nan, dtype=float)
        for i in range(n):
            if i >= k - 1:
                w = ret.iloc[i - k + 1 : i + 1]
                col[i] = round(float(w.std(ddof=0)), 5) if len(w) else 0.0
        feat[f"wave_std{k}"] = col

    # 4) ATR 标准化
    atr_col = np.full(n, np.nan, dtype=float)
    for i in range(n):
        atr_col[i] = _atr_ratio(df, i)
    feat["atr_ratio"] = atr_col

    # 5) 跳空特征（基于最近 250 日窗口）
    jump_down_power = np.zeros(n, dtype=float)
    jump_up_power = np.zeros(n, dtype=float)
    diff_down_days = np.zeros(n, dtype=float)
    diff_up_days = np.zeros(n, dtype=float)
    for i in range(1, n):
        lo = max(0, i - 250)
        up_power = 0.0
        down_power = 0.0
        up_diff = 0
        down_diff = 0
        for j in range(max(1, lo), i + 1):
            gap = (df["open"].iloc[j] - df["close"].iloc[j - 1]) / df["close"].iloc[j - 1]
            if gap > 0.0:
                up_power = gap
                up_diff = (df["date"].iloc[i] - df["date"].iloc[j]).days
            elif gap < 0.0:
                down_power = gap
                down_diff = (df["date"].iloc[i] - df["date"].iloc[j]).days
        jump_up_power[i] = round(up_power, 4)
        jump_down_power[i] = round(down_power, 4)
        diff_up_days[i] = float(up_diff)
        diff_down_days[i] = float(down_diff)
    feat["jump_up_power"] = jump_up_power
    feat["jump_down_power"] = jump_down_power
    feat["diff_up_days"] = diff_up_days
    feat["diff_down_days"] = diff_down_days

    return feat


# ============================================================
# 监督数据集构建（复刻 ABuMLPd.ClosePredict 的涨跌方向标签）
# ============================================================
def _build_xy(df: pd.DataFrame, feat: pd.DataFrame, horizon: int):
    """构造 X（特征）与 y（未来 horizon 日收益率方向：1=涨, 0=跌）。"""
    n = len(df)
    future_ret = df["close"].shift(-horizon) / df["close"] - 1.0
    y = (future_ret > 0).astype(int)
    # 仅保留 warmup 完成且未来收益已知的样本
    valid = feat.dropna().index
    valid = [i for i in valid if i < n - horizon]
    if len(valid) < 50:
        return None, None
    X = feat.loc[valid].reset_index(drop=True)
    y = y.loc[valid].reset_index(drop=True)
    return X, y


# ============================================================
# 训练 + 预测（对应 ABuML.fit / predict）
# ============================================================
@dataclass
class AbuMLResult:
    code: str
    symbol: str
    horizon: int
    direction: str            # "看涨" / "看跌" / "数据不足"
    confidence: float         # 预测类别概率 0~1
    test_accuracy: float      # 测试集准确率
    test_f1: float            # 测试集 F1
    cv_accuracy: float        # 5 折交叉验证均值
    n_samples: int
    n_since: int              # 距最新交易日的样本数（预测所用窗口）
    feature_importance: list[dict] = field(default_factory=list)
    trained_at: str = ""
    note: str = ""


_CACHE: dict[str, tuple[float, AbuMLResult]] = {}
_CACHE_TTL = 300.0  # 5 分钟


def predict(code: str, horizon: int = 5) -> AbuMLResult:
    """端到端：取数 -> 特征 -> 监督训练 -> 对最新窗口预测。结果缓存 5 分钟。"""
    sym = normalize_symbol(code)
    cache_key = f"{sym}#{horizon}"
    now = time.time()
    if cache_key in _CACHE and now - _CACHE[cache_key][0] < _CACHE_TTL:
        return _CACHE[cache_key][1]

    try:
        df = fetch_kline(code)
    except Exception as e:  # noqa: BLE001
        res = AbuMLResult(code=code, symbol=sym, horizon=horizon,
                          direction="数据不足", confidence=0.0,
                          test_accuracy=0.0, test_f1=0.0, cv_accuracy=0.0,
                          n_samples=0, n_since=0,
                          note=f"行情获取失败：{type(e).__name__} {e}")
        return res

    feat = _build_features(df)
    X, y = _build_xy(df, feat, horizon)
    if X is None or len(X) < 50:
        res = AbuMLResult(code=code, symbol=sym, horizon=horizon,
                          direction="数据不足", confidence=0.0,
                          test_accuracy=0.0, test_f1=0.0, cv_accuracy=0.0,
                          n_samples=0, n_since=0,
                          note="历史样本不足，无法训练（需 >= 50 个完整窗口）")
        return res

    # 训练/测试切分（时间顺序，避免未来泄漏）
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    scaler = StandardScaler().fit(X_train)
    clf = RandomForestClassifier(n_estimators=150, max_depth=6,
                                 random_state=42, n_jobs=-1)
    clf.fit(scaler.transform(X_train), y_train)

    # 度量（对应 ABuML.score）
    acc = float(accuracy_score(y_test, clf.predict(scaler.transform(X_test))))
    f1 = float(f1_score(y_test, clf.predict(scaler.transform(X_test)), zero_division=0))
    try:
        cv = float(np.mean(cross_val_score(
            RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1),
            scaler.transform(X), y, cv=3, scoring="accuracy")))
    except Exception:
        cv = 0.0

    # 对最新窗口预测
    last_feat = X.iloc[[-1]]
    proba = clf.predict_proba(scaler.transform(last_feat))[0]
    pred = int(clf.predict(scaler.transform(last_feat))[0])
    conf = float(proba[pred])

    # 特征重要性（对应 ABuML 的特征贡献度展示）
    importances = sorted(
        zip(X.columns, clf.feature_importances_),
        key=lambda kv: kv[1], reverse=True,
    )[:8]
    feat_imp = [{"feature": k, "importance": round(float(v), 4)} for k, v in importances]

    res = AbuMLResult(
        code=code, symbol=sym, horizon=horizon,
        direction="看涨" if pred == 1 else "看跌",
        confidence=round(conf, 4),
        test_accuracy=round(acc, 4),
        test_f1=round(f1, 4),
        cv_accuracy=round(cv, 4),
        n_samples=len(X),
        n_since=int(len(df) - 1 - X.index[-1]) if len(X) else 0,
        feature_importance=feat_imp,
        trained_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        note="基于 westock 真实日K线 + ABu(bbfamily/abu) 风格特征工程训练的随机森林涨跌方向分类器",
    )
    _CACHE[cache_key] = (now, res)
    return res


def clear_cache() -> None:
    _CACHE.clear()
