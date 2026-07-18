"""Stock Detail Service — 聚合个股资料、财报、新闻、实时动态

通过 westock-data CLI 并行拉取 profile / finance / news / marketnews 四个数据源，
合并为单次 API 响应供前端详情面板使用。
"""
import json
import time
import threading
from typing import Optional

from app.services.westock_client import _run, parse_markdown_table, WeStockError

# ---------- 缓存 ----------
_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 120  # 秒


def _safe_run(*args: str, timeout: int = 12) -> list[dict]:
    """执行 westock-data 命令并解析为表格，失败返回空列表。"""
    try:
        return parse_markdown_table(_run(list(args), timeout=timeout))
    except WeStockError:
        return []


def _parse_finance_raw(raw: str) -> dict[str, list[dict]]:
    """解析 finance 命令的多段 Markdown 输出（lrb/zcfz/xjll + 可选指标段）。"""
    sections: dict[str, list[dict]] = {}
    blocks = raw.split("\n\n")
    current_label = ""
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # 检查是否是新段标题（**xxx**）
        for line in block.splitlines():
            s = line.strip()
            if s.startswith("**") and s.endswith("**"):
                current_label = s.strip("*").strip()
                break
        if current_label:
            rows = parse_markdown_table(block)
            if rows:
                sections.setdefault(current_label, []).extend(rows)
    return sections


def _normalize_code(code: str) -> str:
    """将各种代码格式统一为 westock-data 可识别的格式。

    600519.SH → sh600519
    300750.SZ → sz300750
    sh600519  → sh600519
    0700.HK   → hk00700
    """
    code = code.strip()
    if "." in code:
        num, mkt = code.split(".", 1)
        mkt = mkt.upper()
        mapping = {"SH": "sh", "SZ": "sz", "BJ": "bj", "HK": "hk"}
        prefix = mapping.get(mkt, mkt.lower())
        return f"{prefix}{num}"
    return code


def get_stock_detail(code: str, force: bool = False) -> dict:
    """获取个股完整详情（并行版）。

    Args:
        code: 股票代码，支持 600519.SH / sz300043 / sh600519 / hk00700
        force: 是否跳过缓存强制刷新

    Returns:
        {
            "code": "sz300043",
            "name": "星辉娱乐",
            "timestamp": "2026-07-13T17:00:00",
            "profile": {...},
            "finance": {"lrb": [...], "zcfz": [...], "xjll": [...]},
            "news": [...],
            "marketNews": [...]
        }
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    normalized = _normalize_code(code)
    now = time.time()
    cache_key = normalized

    with _cache_lock:
        if not force and cache_key in _cache and (now - _cache[cache_key].get("_ts", 0)) < CACHE_TTL:
            return _cache[cache_key]

    # 并行拉取 4 个数据源
    def _fetch_finance():
        try:
            raw = _run(["finance", normalized, "--num", "4"], timeout=15)
            return _parse_finance_raw(raw)
        except WeStockError:
            return {}

    results: dict = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(_safe_run, "profile", normalized): "profile",
            ex.submit(_fetch_finance): "finance",
            ex.submit(_safe_run, "news", normalized): "news",
            ex.submit(_safe_run, "marketnews", normalized): "marketNews",
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                results[label] = future.result()
            except Exception:
                results[label] = [] if label != "finance" else {}

    profile_rows = results.get("profile", [])
    finance = results.get("finance", {})
    news_rows = results.get("news", [])
    market_news_rows = results.get("marketNews", [])

    profile = profile_rows[0] if profile_rows else {}
    name = profile.get("name", code)

    result = {
        "code": normalized,
        "name": name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "profile": profile,
        "finance": {
            "lrb": finance.get("lrb", []),
            "zcfz": finance.get("zcfz", []),
            "xjll": finance.get("xjll", []),
        },
        "news": news_rows,
        "marketNews": market_news_rows,
        "_ts": now,
    }

    with _cache_lock:
        _cache[cache_key] = result
    return result
