"""A股实时动态服务 — 聚合 westock-data 的多维度盘面数据。

数据源（均来自腾讯自选股实时接口）：
  - hot         → 热门个股（含涨跌幅）
  - lhb         → 龙虎榜（机构/游资席位）
  - sector rank → 板块涨跌排行
  - asfund      → 主力资金净流向
  - marketnews  → 实时快讯
"""

import time
import concurrent.futures as _cf
from app.services.westock_client import run_table, WeStockError

CACHE: dict[str, tuple[float, object]] = {}
CACHE_TTL = 20  # 秒（原 30，缩短以提升数据实时性）

# 后台刷新状态追踪（避免多个请求同时触发刷新）
_REFRESHING: set[str] = set()


def _cached(key: str, fetcher, ttl: int = CACHE_TTL, *, serve_stale: bool = False):
    """本地内存缓存，可选的 stale-while-revalidate 模式。

    当 serve_stale=True 时：如果缓存未过期优先返回缓存；如果已过期但没人在刷新，
    触发后台刷新并立即返回旧值（避免阻塞请求线程）。
    """
    now = time.time()
    if key in CACHE:
        ts, val = CACHE[key]
        if now - ts < ttl:
            return val
        # 缓存已过期 — 如果允许 stale，立即返回旧值 + 后台刷新
        if serve_stale and key not in _REFRESHING:
            _REFRESHING.add(key)
            import threading
            def _bg_refresh():
                try:
                    CACHE[key] = (time.time(), fetcher())
                except Exception:
                    pass
                finally:
                    _REFRESHING.discard(key)
            threading.Thread(target=_bg_refresh, daemon=True).start()
            return val

    # 首次或无缓存 — 直接获取
    val = fetcher()
    CACHE[key] = (now, val)
    return val


def _to_float(v, default=0.0):
    try:
        if v in (None, "", "-"):
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _is_ashare(code: str) -> bool:
    """判断是否为 A 股代码（沪/深/北），并排除 ETF（避免美股/港股/基金混入"大A"列表）。

    - 前缀 sh/sz/bj 视为 A 股候选
    - 上交所 ETF 以 51/58 开头，深交所 ETF 以 15/16 开头 → 排除
    """
    if not code:
        return False
    if not (code.startswith("sh") or code.startswith("sz") or code.startswith("bj")):
        return False
    num = code[2:]
    if code.startswith("sh") and (num.startswith("51") or num.startswith("58")):
        return False
    if code.startswith("sz") and (num.startswith("15") or num.startswith("16")):
        return False
    return True


# ============================================================
# 热门个股
# ============================================================
def get_hot_stocks(limit: int = 15) -> list[dict]:
    """获取热门个股列表（基于搜索热度排名）。"""

    def _fetch():
        rows = run_table(["hot"], timeout=12)
        if not rows:
            raise WeStockError("热门个股数据为空")
        items = []
        for r in rows:
            code = r.get("code", "")
            # 仅保留 A 股（剔除美股/港股/ETF），确保"大A实时动态"纯净
            if not _is_ashare(code):
                continue
            items.append({
                "code": code,
                "name": r.get("name", ""),
                "changePct": _to_float(r.get("zdf")),
                "price": _to_float(r.get("zxj")),
                "type": r.get("stock_type", "GP-A"),
            })
            if len(items) >= limit:
                break
        if not items:
            raise WeStockError("热门个股无 A 股数据")
        return items

    try:
        return _cached("hot_stocks", _fetch)
    except WeStockError:
        return []


# ============================================================
# 龙虎榜
# ============================================================
def get_lhb(limit: int = 15) -> list[dict]:
    """获取龙虎榜数据（机构席位）。已按 code 去重，取最高排名条目。"""

    def _fetch():
        rows = run_table(["lhb"], timeout=15)
        if not rows:
            raise WeStockError("龙虎榜数据为空")
        items = []
        seen: set[str] = set()
        for r in rows:
            code = r.get("代码", "")
            if not code or code in seen:
                continue
            seen.add(code)
            items.append({
                "code": code,
                "name": r.get("名称", ""),
                "rank": int(r.get("排名", 0) or 0),
                "daysOnList": int(r.get("上榜天数", 0) or 0),
                "instSeats": int(r.get("机构买入席位", 0) or 0),
                "instBuyAmt": r.get("机构买入额", "—"),
                "buyRatio": r.get("买入占比", "—"),
                "totalBuyAmt": r.get("总买入额", "—"),
                "netBuyAmt": r.get("净买入额", "—"),
                "netRatio": r.get("净占比", "—"),
            })
            if len(items) >= limit:
                break
        return items

    try:
        return _cached("lhb", _fetch)
    except WeStockError:
        return []


# ============================================================
# 板块涨跌排名
# ============================================================
def get_sector_rankings(limit: int = 31) -> list[dict]:
    """获取申万一级行业区间涨幅排名。"""

    def _fetch():
        rows = run_table(
            ["sector", "--rank", "interval_chg_rank_sw1", "--sort", "chg5Days"],
            timeout=15,
        )
        if not rows:
            raise WeStockError("板块排名数据为空")
        items = []
        for r in rows[:limit]:
            items.append({
                "code": r.get("代码", ""),
                "name": r.get("名称", ""),
                "chg5d": _to_float(r.get("5日%")),
                "chg20d": _to_float(r.get("20日%")),
                "chg60d": _to_float(r.get("60日%")),
                "chg120d": _to_float(r.get("120日%")),
                "chg250d": _to_float(r.get("250日%")),
            })
        return items

    try:
        return _cached("sector_rank", _fetch)
    except WeStockError:
        return []


# ============================================================
# 主力资金流向
# ============================================================
def get_capital_flow() -> dict:
    """获取上证指数主力资金净流向（主力/超大单/中单/小单）。"""

    def _fetch():
        rows = run_table(["asfund", "sh000001"], timeout=12)
        if not rows:
            raise WeStockError("资金流向数据为空")
        r = rows[0]
        return {
            "date": r.get("EndDate", ""),
            "mainNetFlow": _to_float(r.get("MainNetFlow")),         # 主力净流入
            "jumboNetFlow": _to_float(r.get("JumboNetFlow")),       # 超大单净流入
            "midNetFlow": _to_float(r.get("MidNetFlow")),           # 中单净流入
            "smallNetFlow": _to_float(r.get("SmallNetFlow")),       # 小单净流入
            "mainNetFlow5d": _to_float(r.get("MainNetFlow5D")),     # 5日主力净流入
            "mainNetFlow20d": _to_float(r.get("MainNetFlow20D")),   # 20日主力净流入
        }

    try:
        return _cached("capital_flow", _fetch)
    except WeStockError:
        return {
            "date": "", "mainNetFlow": 0, "jumboNetFlow": 0,
            "midNetFlow": 0, "smallNetFlow": 0,
            "mainNetFlow5d": 0, "mainNetFlow20d": 0,
        }


# ============================================================
# 全市场指数行情
# ============================================================
MARKET_INDICES = [
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
    ("sh000688", "科创50"),
    ("sh000300", "沪深300"),
    ("sh000016", "上证50"),
    ("sh000905", "中证500"),
    ("sh000852", "中证1000"),
]

INDEX_ORDER = {code: i for i, (code, _) in enumerate(MARKET_INDICES)}
INDEX_NAMES = {code: name for code, name in MARKET_INDICES}


def get_market_indices() -> list[dict]:
    """获取全市场核心指数实时行情（批量查询，一次 CLI 调用）。"""

    def _fetch():
        codes = ",".join(c for c, _ in MARKET_INDICES)
        try:
            rows = run_table(["quote", codes], timeout=15)
        except WeStockError:
            return []

        if not rows:
            return []

        results = []
        for r in rows:
            code = r.get("code", "")
            if not code:
                continue
            results.append({
                "code": code,
                "name": INDEX_NAMES.get(code, code),
                "price": _to_float(r.get("price")),
                "change": _to_float(r.get("change")),
                "changePct": _to_float(r.get("change_percent")),
                "volume": _to_float(r.get("volume"), 0),
                "amount": _to_float(r.get("amount"), 0),
            })
        # 按预定义顺序排列
        results.sort(key=lambda x: INDEX_ORDER.get(x["code"], 99))
        return results

    return _cached("market_indices", _fetch, ttl=10, serve_stale=True)


# ============================================================
# 个股涨跌排行（涨幅榜 / 跌幅榜 / 成交额榜）
# ============================================================
def get_stock_rankings() -> dict:
    """获取个股涨跌排行：涨幅榜 Top 10、跌幅榜 Top 10（仅 A 股，按涨跌幅排序）。"""

    def _fetch():
        rows = run_table(["hot"], timeout=15)
        if not rows:
            return {"topGainers": [], "topLosers": [], "topVolume": []}

        # 仅保留 A 股，构造统一结构
        stocks: list[dict] = []
        for r in rows:
            code = r.get("code", "")
            if not _is_ashare(code):
                continue
            stocks.append({
                "code": code,
                "name": r.get("name", ""),
                "price": _to_float(r.get("zxj")),
                "changePct": _to_float(r.get("zdf")),
            })
        if not stocks:
            return {"topGainers": [], "topLosers": [], "topVolume": []}

        # 涨幅榜：按涨跌幅降序
        top_gainers = sorted(stocks, key=lambda x: x["changePct"], reverse=True)[:10]
        # 跌幅榜：按涨跌幅升序
        top_losers = sorted(stocks, key=lambda x: x["changePct"])[:10]

        return {
            "topGainers": top_gainers,
            "topLosers": top_losers,
            "topVolume": [],
        }

    return _cached("stock_rankings", _fetch, ttl=15, serve_stale=True)


# ============================================================
# 实时公告资讯
# ============================================================
def get_market_news(limit: int = 20) -> list[dict]:
    """获取 A 股市场实时快讯公告。"""

    def _fetch():
        rows = run_table(["marketnews", "--limit", str(limit)], timeout=12)
        if not rows:
            raise WeStockError("市场快讯为空")
        items = []
        for r in rows[:limit]:
            items.append({
                "time": r.get("time", ""),
                "title": r.get("title", ""),
                "source": r.get("source", ""),
                "summary": r.get("summary", "")[:120],
                "type": r.get("type", "快讯"),
            })
        return items

    try:
        return _cached("market_news", _fetch, ttl=30)
    except WeStockError:
        return []


# ============================================================
# 市场宽度 / 涨跌统计（v1.3.1 新增）
# ============================================================
def get_market_breadth() -> dict:
    """获取全市场涨跌家数统计及分布（沪深全 A 口径）。

    数据源：westock-data changedist hs（沪深两市合并口径，含涨停/跌停家数）。
    注意：changedist 仅支持沪深聚合（hs），不支持单独按 sh/sz 拆分，
    故 shanghai/shenzhen 置空，仅呈现 aggregate（沪深合计）。
    """

    def _fetch():
        rows = run_table(["changedist", "hs"], timeout=15)
        if not rows:
            raise WeStockError("涨跌分布数据为空")
        summary = rows[0]
        total = int(summary.get("总数", 0) or 0)
        up_count = int(summary.get("上涨", 0) or 0)
        down_count = int(summary.get("下跌", 0) or 0)
        flat_count = int(summary.get("平盘", 0) or 0)
        limit_up = int(summary.get("涨停", 0) or 0)
        limit_down = int(summary.get("跌停", 0) or 0)
        date_str = summary.get("日期", "")
        breadth_pct = round(up_count / total * 100, 1) if total > 0 else 0.0
        if total == 0:
            raise WeStockError("涨跌分布总数为 0")
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "date": date_str,
            "shanghai": None,
            "shenzhen": None,
            "aggregate": {
                "total": total,
                "upCount": up_count,
                "downCount": down_count,
                "flatCount": flat_count,
                "limitUp": limit_up,
                "limitDown": limit_down,
                "breadthPct": breadth_pct,
            },
        }

    try:
        return _cached("market_breadth", _fetch, ttl=15)
    except WeStockError:
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "date": "",
            "shanghai": None,
            "shenzhen": None,
            "aggregate": {"total": 0, "upCount": 0, "downCount": 0, "flatCount": 0,
                          "limitUp": 0, "limitDown": 0, "breadthPct": 0},
        }


# ============================================================
# 聚合全部动态（v2.1 — 全并行 + stale-while-revalidate）
# ============================================================
def get_all_dynamics() -> dict:
    """聚合全部 A 股实时动态数据 — 所有子模块并行执行，带后台缓存刷新。

    总耗时 ≈ max(单次最慢子模块) 而非 sum(所有子模块)。
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    results: dict = {}

    # 定义子任务（批获取模式，复用缓存）
    def _indices():
        results["marketIndices"] = get_market_indices()

    def _rankings():
        results["stockRankings"] = get_stock_rankings()

    def _hot():
        results["hotStocks"] = get_hot_stocks(15)

    def _lhb():
        results["lhb"] = get_lhb(12)

    def _sectors():
        results["sectorRankings"] = get_sector_rankings(31)

    def _capital():
        results["capitalFlow"] = get_capital_flow()

    def _news():
        results["marketNews"] = get_market_news(15)

    def _breadth():
        results["marketBreadth"] = get_market_breadth()

    # 全部并行
    with _cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [
            ex.submit(fn)
            for fn in (_indices, _rankings, _hot, _lhb, _sectors, _capital, _news, _breadth)
        ]
        for fut in _cf.as_completed(futs):
            try:
                fut.result()
            except Exception:
                pass  # 单个失败不影响整体

    # 兜底：确保所有字段存在
    results.setdefault("marketIndices", [])
    results.setdefault("stockRankings", {"topGainers": [], "topLosers": [], "topVolume": []})
    results.setdefault("hotStocks", [])
    results.setdefault("lhb", [])
    results.setdefault("sectorRankings", [])
    results.setdefault("capitalFlow", {
        "date": "", "mainNetFlow": 0, "jumboNetFlow": 0,
        "midNetFlow": 0, "smallNetFlow": 0,
        "mainNetFlow5d": 0, "mainNetFlow20d": 0,
    })
    results.setdefault("marketNews", [])
    results.setdefault("marketBreadth", {
        "timestamp": timestamp, "date": "",
        "shanghai": None, "shenzhen": None,
        "aggregate": {"total": 0, "upCount": 0, "downCount": 0, "flatCount": 0,
                       "limitUp": 0, "limitDown": 0, "breadthPct": 50},
    })

    return {"timestamp": timestamp, **results}
