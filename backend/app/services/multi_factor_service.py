"""多因子股票评分引擎 — 五维因子模型 + 全市场百分位排名。

架构：
- 估值(Value): PE/PB/股息率 — 来自 westock quote
- 质量(Quality): 毛利率/净利率/经营利润率 — 来自 westock finance
- 动量(Momentum): 1M/3M/YTD 收益 — 来自 westock quote
- 波动(Volatility): 年化波动/最大回撤/Beta — 来自 westock kline
- 情绪(Sentiment): 换手率/量比 — 来自 westock quote

算法：
- 子因子 → z-score 标准化 → 维度内等权 → cdf → 0-100 评分
- 截面内百分位排名
- 缓存 10 分钟（截面计算较重）

防未来函数：
- 因子计算仅使用 t 日及之前数据；quote/finance 均为最新财报窗口期内公开数据。

免责声明：本模块为模型驱动的量化研究工具，结果不构成任何投资建议。
"""
from __future__ import annotations

import concurrent.futures as _cf
import time
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import stats

from app.services import westock_client as ws

# ============================================================
# 常量
# ============================================================
FACTOR_DIMS = ["value", "quality", "momentum", "volatility", "sentiment"]
FACTOR_LABELS_ZH = {
    "value": "估值",
    "quality": "质量",
    "momentum": "动量",
    "volatility": "波动",
    "sentiment": "情绪",
}

# 截面计算缓存（key → (timestamp, MultiFactorUniverse)）
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 600.0  # 10 分钟

# K 线拉取长度（约 1 年，足够计算波动率）
_KLINE_LIMIT = 252

# 截面计算所需的最少有效股票数
_MIN_UNIVERSE_SIZE = 10


# ============================================================
# 数据结构
# ============================================================
@dataclass
class FactorScore:
    """单只股票的多因子评分完整结果。"""
    code: str
    name: str = ""
    industry: str = ""
    # 综合
    totalScore: float = 0.0       # 0-100
    percentile: float = 0.0       # 全市场百分位
    rank: int = 0                 # 全市场排名（1 为最优）
    universeSize: int = 0
    # 五维得分
    dimensions: dict = field(default_factory=dict)  # {dim: {score, label, subFactors: {...}}}
    # 元数据
    dataTimestamp: str = ""
    note: str = ""


# ============================================================
# 数据获取
# ============================================================
def _safe_float(v, default=0.0) -> float:
    """安全转换，处理 None/NaN/空。"""
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _fetch_quote(code: str) -> dict:
    """获取 quote 数据：PE/PB/股息/动量/换手率/市值等。"""
    rows = ws.run_table(["quote", code], timeout=15)
    if not rows:
        return {}
    r = rows[0]
    return {
        "pe": _safe_float(r.get("pe_ratio")),
        "pb": _safe_float(r.get("pb_ratio")),
        "dividend": _safe_float(r.get("dividend_ratio_ttm")),
        "marketCap": _safe_float(r.get("total_market_cap")),
        "chg5d": _safe_float(r.get("chg_5d")),
        "chg10d": _safe_float(r.get("chg_10d")),
        "chg20d": _safe_float(r.get("chg_20d")),
        "chg60d": _safe_float(r.get("chg_60d")),
        "chgYtd": _safe_float(r.get("chg_ytd")),
        "turnoverRate": _safe_float(r.get("turnover_rate")),
        "volumeRatio": _safe_float(r.get("volume_ratio")),
    }


def _fetch_finance(code: str) -> dict:
    """获取最新一期财务数据：毛利率/净利率/经营利润率。"""
    rows = ws.run_table(["finance", code, "--num", "1"], timeout=15)
    if not rows:
        return {}
    r = rows[0]
    rev = _safe_float(r.get("OperatingRevenueTTM"), 1.0)
    gp = _safe_float(r.get("GrossProfitTTM"))
    np_val = _safe_float(r.get("NPParentCompanyOwnersTTM"))
    op = _safe_float(r.get("OperatingProfitTTM"))
    return {
        "grossMargin": gp / rev if rev > 0 else 0.0,
        "netMargin": np_val / rev if rev > 0 else 0.0,
        "opMargin": op / rev if rev > 0 else 0.0,
    }


def _fetch_kline_vol(code: str) -> dict:
    """从 K 线计算波动率、最大回撤、Beta。"""
    rows = ws.run_table(
        ["kline", code, "--period", "day", "--limit", str(_KLINE_LIMIT), "--fq", "qfq"],
        timeout=20,
    )
    if not rows or len(rows) < 60:
        return {"volatility": 0.0, "maxDrawdown": 0.0, "beta": 1.0}
    closes = np.array([_safe_float(r.get("last")) for r in rows], dtype=float)
    closes = closes[closes > 0]
    if len(closes) < 60:
        return {"volatility": 0.0, "maxDrawdown": 0.0, "beta": 1.0}
    # 日收益率
    rets = np.diff(closes) / closes[:-1]
    # 年化波动率
    ann_vol = float(np.std(rets, ddof=1) * math.sqrt(252))
    # 最大回撤
    peak = np.maximum.accumulate(closes)
    dd = (peak - closes) / peak
    max_dd = float(np.max(dd))
    # Beta（对等权指数近似：个股收益 vs 自身均值回归 → 使用市场模型简化）
    # 此处 Beta 为简化估算：若 close 序列可用，用 60 日滚动
    beta = 1.0
    if len(rets) >= 60:
        # 使用 close 序列的波动相对于整体市场波动的比例作为简化 beta
        # 更精确的 beta 需要指数 K 线，但批量计算时性能开销太大
        mkt_vol = 0.20  # A 股年均波动约 20%
        beta = ann_vol / mkt_vol if mkt_vol > 0 else 1.0
        beta = max(0.2, min(beta, 3.0))  # clamp
    return {"volatility": ann_vol, "maxDrawdown": max_dd, "beta": beta}


def _fetch_profile(code: str) -> dict:
    """获取行业分类。"""
    rows = ws.run_table(["profile", code], timeout=10)
    if not rows:
        return {"industry": "", "name": ""}
    r = rows[0]
    return {
        "name": str(r.get("name", "")),
        "industry": str(r.get("industry", "")),
    }


def _fetch_all(code: str) -> dict:
    """并行拉取单只股票全部所需数据。"""
    results: dict = {"code": code}

    def _quote():
        results["quote"] = _fetch_quote(code)

    def _finance():
        results["finance"] = _fetch_finance(code)

    def _kline():
        results["kline"] = _fetch_kline_vol(code)

    def _profile():
        results["profile"] = _fetch_profile(code)

    with _cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(f) for f in (_quote, _finance, _kline, _profile)]
        for fut in _cf.as_completed(futs):
            try:
                fut.result()
            except Exception:
                pass

    return results


# ============================================================
# 因子值提取与标准化
# ============================================================
# direction: +1 = 值越大越好, -1 = 值越小越好（score 计算时取相反的 z-score）
FACTOR_DIRECTION = {
    # Value — lower PE/PB better, higher dividend better
    "pe": -1, "pb": -1, "dividend": +1,
    # Quality — all higher better
    "grossMargin": +1, "netMargin": +1, "opMargin": +1,
    # Momentum — all higher better
    "chg20d": +1, "chg60d": +1, "chgYtd": +1,
    # Volatility — lower better (low-vol premium)
    "volatility": -1, "maxDrawdown": -1, "beta": -1,
    # Sentiment — moderate turnover/volume preferred (not extreme)
    "turnoverRate": 0, "volumeRatio": 0,
}

SUB_FACTORS = {
    "value": ["pe", "pb", "dividend"],
    "quality": ["grossMargin", "netMargin", "opMargin"],
    "momentum": ["chg20d", "chg60d", "chgYtd"],
    "volatility": ["volatility", "maxDrawdown", "beta"],
    "sentiment": ["turnoverRate", "volumeRatio"],
}


def _extract_raw_factors(data: dict) -> dict[str, float]:
    """从采集的原始数据中提取所有子因子值。"""
    q = data.get("quote", {})
    f = data.get("finance", {})
    k = data.get("kline", {})
    return {
        # Value
        "pe": q.get("pe", 0),
        "pb": q.get("pb", 0),
        "dividend": q.get("dividend", 0),
        # Quality
        "grossMargin": f.get("grossMargin", 0),
        "netMargin": f.get("netMargin", 0),
        "opMargin": f.get("opMargin", 0),
        # Momentum
        "chg20d": q.get("chg20d", 0),
        "chg60d": q.get("chg60d", 0),
        "chgYtd": q.get("chgYtd", 0),
        # Volatility
        "volatility": k.get("volatility", 0),
        "maxDrawdown": k.get("maxDrawdown", 0),
        "beta": k.get("beta", 0),
        # Sentiment
        "turnoverRate": q.get("turnoverRate", 0),
        "volumeRatio": q.get("volumeRatio", 0),
    }


def _is_valid(raw: dict[str, float]) -> bool:
    """判断因子数据是否有效（至少估值+动量有数据，PE/PB > 0）。"""
    if raw.get("pe", 0) <= 0 and raw.get("pb", 0) <= 0:
        return False
    return True


# ============================================================
# 截面评分
# ============================================================
def _zscore(arr: np.ndarray) -> np.ndarray:
    """安全的 z-score 标准化。"""
    mu = np.nanmean(arr)
    sd = np.nanstd(arr)
    if sd < 1e-12:
        return np.zeros_like(arr)
    return (arr - mu) / sd


def _score_universe(stock_factors: list[dict]) -> list[dict]:
    """对一篮子股票的因子值做截面标准化 + 评分。

    Args:
        stock_factors: [{code, name, industry, raw: {sub_factor: value}, ...}, ...]

    Returns:
        同上列表，额外附加 scores / totalScore / percentile / rank 字段。
    """
    n = len(stock_factors)
    if n < 3:
        return stock_factors

    # 构建因子矩阵 (n_stocks × n_sub_factors)
    all_sub_keys = []
    for dim in FACTOR_DIMS:
        all_sub_keys.extend(SUB_FACTORS[dim])

    matrix = np.zeros((n, len(all_sub_keys)))
    for i, sf in enumerate(stock_factors):
        raw = sf.get("raw", {})
        for j, key in enumerate(all_sub_keys):
            matrix[i, j] = raw.get(key, 0.0)

    # Z-score 标准化每个子因子
    z_matrix = np.zeros_like(matrix)
    for j in range(len(all_sub_keys)):
        col = matrix[:, j]
        z_matrix[:, j] = _zscore(col)

    # 维度聚合 + 定向 + CDF 转 0-100
    for i, sf in enumerate(stock_factors):
        dim_scores: dict = {}
        dim_z_sum = 0.0

        for dim in FACTOR_DIMS:
            sub_keys = SUB_FACTORS[dim]
            z_vals = []
            for sk in sub_keys:
                j = all_sub_keys.index(sk)
                direction = FACTOR_DIRECTION.get(sk, 0)
                if direction == 0:
                    # 情绪因子：距离均值越近越好（绝对值取反）
                    z_vals.append(-abs(z_matrix[i, j]))
                elif direction > 0:
                    z_vals.append(z_matrix[i, j])
                else:
                    z_vals.append(-z_matrix[i, j])

            dim_z = np.mean(z_vals) if z_vals else 0.0
            # CDF 转 0-100
            dim_score = round(float(stats.norm.cdf(dim_z) * 100), 1)
            dim_scores[dim] = {
                "score": dim_score,
                "label": FACTOR_LABELS_ZH.get(dim, dim),
                "subFactors": {
                    sk: round(float(stats.norm.cdf(
                        -abs(z_matrix[i, all_sub_keys.index(sk)])
                        if FACTOR_DIRECTION.get(sk, 0) == 0
                        else z_matrix[i, all_sub_keys.index(sk)] * FACTOR_DIRECTION.get(sk, 1)
                    ) * 100), 1)
                    for sk in sub_keys
                },
            }
            dim_z_sum += dim_z

        # 综合：五维等权 z-score 均值 → CDF → 0-100
        avg_z = dim_z_sum / len(FACTOR_DIMS)
        total = round(float(stats.norm.cdf(avg_z) * 100), 1)
        sf["dimensions"] = dim_scores
        sf["totalScore"] = total

    # 按总分排名
    scores = [sf["totalScore"] for sf in stock_factors]
    order = np.argsort(scores)[::-1]  # 降序

    for rank_idx, orig_idx in enumerate(order):
        sf = stock_factors[orig_idx]
        sf["rank"] = rank_idx + 1
        sf["percentile"] = round((1.0 - rank_idx / max(n - 1, 1)) * 100, 1)

    return stock_factors


# ============================================================
# 公开 API
# ============================================================
def score_stock(code: str, universe_codes: Optional[list[str]] = None) -> FactorScore:
    """单只股票多因子评分（需要在截面中计算，故需 universe）。

    若无 universe，自动使用沪深300成份股作为截面基准。
    """
    code = _normalize(code)
    if universe_codes is None:
        universe_codes = _get_default_universe(50)
    if code not in universe_codes:
        universe_codes = [code] + universe_codes

    cache_key = f"score:{code}:{len(universe_codes)}"
    now = time.time()
    if cache_key in _CACHE and now - _CACHE[cache_key][0] < _CACHE_TTL:
        cached = _CACHE[cache_key][1]
        if isinstance(cached, FactorScore):
            return cached

    # 计算全截面
    universe = batch_score(universe_codes)
    for item in universe:
        if item.code == code:
            _CACHE[cache_key] = (now, item)
            return item

    # fallback：返回空结果
    profile = _fetch_profile(code)
    return FactorScore(
        code=code, name=profile.get("name", code), industry=profile.get("industry", ""),
        note="截面计算失败，无法生成评分",
    )


def batch_score(codes: list[str]) -> list[FactorScore]:
    """批量多因子评分（自动构建截面并排名）。

    流程：
    1. 并行拉取每只股票的 quote / finance / kline / profile
    2. 提取原始因子值
    3. 截面 z-score 标准化 + 维度聚合 + 百分位排名
    """
    codes = [_normalize(c) for c in codes if c and c.strip()]
    if not codes:
        return []

    cache_key = f"batch:{','.join(sorted(codes))}"
    now = time.time()
    if cache_key in _CACHE and now - _CACHE[cache_key][0] < _CACHE_TTL:
        return _CACHE[cache_key][1]

    # 并行拉取
    stock_data: dict[str, dict] = {}

    def _work(c: str):
        try:
            stock_data[c] = _fetch_all(c)
        except Exception:
            stock_data[c] = {"code": c, "error": True}

    with _cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_work, c): c for c in codes}
        for fut in _cf.as_completed(futs):
            try:
                fut.result()
            except Exception:
                pass

    # 提取因子值 + 过滤无效
    stock_factors = []
    for c in codes:
        sd = stock_data.get(c)
        if not sd or sd.get("error"):
            continue
        raw = _extract_raw_factors(sd)
        if not _is_valid(raw):
            continue
        profile = sd.get("profile", {})
        stock_factors.append({
            "code": c,
            "name": profile.get("name", c),
            "industry": profile.get("industry", ""),
            "raw": raw,
            "marketCap": sd.get("quote", {}).get("marketCap", 0),
        })

    if not stock_factors:
        return []

    # 截面评分
    stock_factors = _score_universe(stock_factors)

    # 转换为 FactorScore
    results = []
    for sf in stock_factors:
        results.append(FactorScore(
            code=sf["code"],
            name=sf.get("name", ""),
            industry=sf.get("industry", ""),
            totalScore=sf.get("totalScore", 0),
            percentile=sf.get("percentile", 0),
            rank=sf.get("rank", 0),
            universeSize=len(stock_factors),
            dimensions=sf.get("dimensions", {}),
            dataTimestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            note="基于 westock quote/finance/kline 真实数据，z-score 截面标准化 + CDF 0-100 评分。五维等权。",
        ))

    _CACHE[cache_key] = (now, results)
    return results


def ranking(
    universe_codes: Optional[list[str]] = None,
    dimension: Optional[str] = None,
    limit: int = 20,
) -> list[FactorScore]:
    """获取因子排名列表。

    Args:
        universe_codes: 股票池，默认沪深300样本
        dimension: 按某维度排序（None = 综合总分）
        limit: 返回前 N 只
    """
    if universe_codes is None:
        universe_codes = _get_default_universe(50)
    scores = batch_score(universe_codes)

    if dimension and dimension in FACTOR_LABELS_ZH:
        scores.sort(key=lambda x: x.dimensions.get(dimension, {}).get("score", 0), reverse=True)
    else:
        scores.sort(key=lambda x: x.totalScore, reverse=True)

    return scores[:limit]


def ic_analysis(
    universe_codes: Optional[list[str]] = None,
    lookback_days: int = 60,
) -> dict:
    """因子截面 IC 分析（简化版：使用当日截面因子值与 quote 中历史收益的秩相关）。

    注：真实 IC 需要多期截面，耗时较长。此处提供当日截面因子值
    与 20 日历史收益的横截面 Spearman 秩相关作为近似。
    """
    if universe_codes is None:
        universe_codes = _get_default_universe(50)
    scores = batch_score(universe_codes)
    if len(scores) < 10:
        return {"note": "有效样本不足", "factors": {}, "sampleSize": len(scores)}

    # 提取各维度得分 + 未来 20 日收益（用 chg20d 作为 proxy）
    dim_keys = list(FACTOR_LABELS_ZH.keys())
    ic_results = {}

    for dim in dim_keys:
        dim_scores = np.array([s.dimensions.get(dim, {}).get("score", 0) for s in scores], dtype=float)
        # 用 chg20d 作为实测收益的近似（非前瞻，chg20d 是过去 20 日收益，因子用最新数据）
        fwd_returns = np.array([
            _fetch_quote(s.code).get("chg20d", 0) for s in scores
        ], dtype=float)

        if len(dim_scores) >= 10 and np.std(dim_scores) > 0 and np.std(fwd_returns) > 0:
            ic, pval = stats.spearmanr(dim_scores, fwd_returns)
            ic_results[dim] = {
                "ic": round(float(ic), 4),
                "pValue": round(float(pval), 4),
                "label": FACTOR_LABELS_ZH.get(dim, dim),
                "significant": bool(pval < 0.05),
            }

    return {
        "factors": ic_results,
        "sampleSize": len(scores),
        "note": "截面因子得分与过去 20 日收益的 Spearman 秩相关（非前瞻 IC，仅作结构参考）",
    }


# ============================================================
# 辅助
# ============================================================
def _normalize(code: str) -> str:
    """标准化为 westock 格式：sh600519。"""
    c = (code or "").strip().lower()
    if not c:
        return ""
    if c[:2] in ("sh", "sz", "bj"):
        return c
    if "." in c:
        num, _, suffix = c.partition(".")
        prefix = {"sh": "sh", "sz": "sz", "bj": "bj"}.get(suffix.lower(), "")
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


def _get_default_universe(size: int = 50) -> list[str]:
    """获取默认截面池（沪深300抽样）。"""
    cache_key = "_universe_hs300"
    now = time.time()
    if cache_key in _CACHE and now - _CACHE[cache_key][0] < _CACHE_TTL * 3:
        cached = _CACHE[cache_key][1]
        if isinstance(cached, list):
            return cached[:size]
    try:
        comp_rows = ws.run_table(["index", "sh000300"], timeout=20)
    except Exception:
        comp_rows = []
    codes = sorted({r["code"] for r in comp_rows if r.get("code")})
    if not codes:
        # 回退：硬编码部分沪深300标的
        codes = [f"sh{str(600000 + i)}" for i in range(size)]
    # 抽样
    if len(codes) > size:
        step = len(codes) / size
        codes = [codes[int(i * step)] for i in range(size)]
    _CACHE[cache_key] = (now, codes)
    return codes


def clear_cache() -> None:
    _CACHE.clear()
