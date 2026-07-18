"""Dashboard API — 交易驾驶舱数据 (V1 + V2六屏矩阵)。

V1 保留兼容旧版；V2 聚合市场温度 / AI研判 / 指数 / 预警 / 资金流向。
"""
from fastapi import APIRouter
from app.services.mock_data import (
    ACCOUNT_METRICS, POSITIONS, INDUSTRY_DIST, STRATEGIES, gen_equity_curve,
)
from app.services import data_provider as dp
from app.db import crud

router = APIRouter()

# 驾驶舱数据缓存（30s TTL）：聚合展示类数据，可接受分钟级延迟；
# 冷启动仍需并行聚合（~3-4s），命中缓存后秒回，大幅降低驾驶舱首屏压力。
DASHBOARD_CACHE: dict = {"data": None, "ts": 0.0}
DASHBOARD_TTL = 30  # 秒

# ============================================================
# V1 — 兼容旧版（保留现有调用）
# ============================================================

@router.get("/")
def get_dashboard():
    """获取驾驶舱全量数据（V1 兼容）"""
    running = [s for s in STRATEGIES if s["status"] == "running"]
    db_report = crud.get_latest_ai_report()
    if db_report:
        report = {
            "sentimentScore": db_report["sentimentScore"],
            "aiJudgment": db_report["aiJudgment"],
        }
    else:
        report = dp.get_ai_report()
    return {
        "account": ACCOUNT_METRICS,
        "indices": dp.get_indices(),
        "positions": POSITIONS,
        "industryDist": INDUSTRY_DIST,
        "sentimentScore": report["sentimentScore"],
        "aiJudgment": report["aiJudgment"],
        "runningStrategies": len(running),
        "runningStrategyList": [
            {"id": s["id"], "name": s["name"], "annualizedReturn": s["annualizedReturn"], "sharpeRatio": s["sharpeRatio"]}
            for s in running
        ],
        "equityCurve": gen_equity_curve(),
        "dataSource": "westock" if dp.data_source_status()["westock_available"] else "mock",
    }

@router.get("/account")
def get_account():
    return ACCOUNT_METRICS

@router.get("/equity-curve")
def get_equity_curve():
    return gen_equity_curve()


# ============================================================
# V2 — 六屏矩阵全量真数据
# ============================================================

def _safe_call(fn, label: str, default=None):
    """安全调用，异常时返回 default 并打印警告。"""
    try:
        return fn()
    except Exception as e:
        import logging
        logging.getLogger("uvicorn").warning(f"DashboardV2[{label}] failed: {e}")
        return default


@router.get("/v2")
def get_dashboard_v2():
    """六屏矩阵全量真实数据（并行版）。

    屏1 (marketOverview) : 市场概览 — 指数 + 温度计
    屏2 (aiJudgment)     : AI 市场研判
    屏3 (klineSignals)   : K 线 + 策略信号（自选股多周期）
    屏4 (capitalFlow)    : 资金流向 — 板块 + 北向 + 融资
    屏5 (riskMonitor)    : 风险监控 — 预警列表 + 风险指标
    屏6 (portfolioPanel) : 组合管理 — 持仓 + 收益概览
    """
    import time
    now = time.time()
    if DASHBOARD_CACHE["data"] is not None and (now - DASHBOARD_CACHE["ts"]) < DASHBOARD_TTL:
        return DASHBOARD_CACHE["data"]
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    futures = {}
    watchlist_codes = ["600519.SH", "300750.SZ", "002594.SZ", "600036.SH"]

    def _get_indices():
        return ("indices", _safe_call(dp.get_indices, "indices", []))

    def _get_temperature():
        try:
            from app.services.market_temperature_service import get_market_temperature
            return ("temperature", _safe_call(get_market_temperature, "temperature", {"score": 50, "riskLevel": "medium", "riskLabel": "--"}))
        except Exception:
            return ("temperature", {"score": 50, "riskLevel": "medium", "riskLabel": "--"})

    def _get_judgment():
        try:
            from app.services.ai_agent_service import generate_market_judgment
            return ("judgment", _safe_call(generate_market_judgment, "judgment", {}))
        except Exception:
            return ("judgment", {})

    def _get_capital_flow():
        try:
            from app.services.market_dynamics_service import get_capital_flow, get_sector_rankings
            return ("capitalFlow", {
                "mainForce": _safe_call(get_capital_flow, "capitalFlow", {}),
                "sectorRankings": _safe_call(lambda: get_sector_rankings(10), "sectorRankings", {}),
            })
        except Exception:
            return ("capitalFlow", {"mainForce": {}, "sectorRankings": {}})

    def _get_alerts():
        try:
            from app.services.alert_engine import get_active_alerts
            return ("alerts", _safe_call(get_active_alerts, "alerts", {"total": 0, "items": []}))
        except Exception:
            return ("alerts", {"total": 0, "items": []})

    def _get_kline(code: str):
        return (f"kline:{code}", _safe_call(lambda: dp.get_stock_kline(code, "day", 40), f"kline:{code}", []))

    # 并行执行所有独立任务（5个模块 + 4条K线 = 9个任务）
    with ThreadPoolExecutor(max_workers=9) as ex:
        futures[ex.submit(_get_indices)] = "indices"
        futures[ex.submit(_get_temperature)] = "temperature"
        futures[ex.submit(_get_judgment)] = "judgment"
        futures[ex.submit(_get_capital_flow)] = "capitalFlow"
        futures[ex.submit(_get_alerts)] = "alerts"
        for code in watchlist_codes:
            futures[ex.submit(_get_kline, code)] = code

        for future in as_completed(futures):
            try:
                key, value = future.result()
                if key.startswith("kline:"):
                    code = key.split(":", 1)[1]
                    results.setdefault("klineSignals", {"watchlist": watchlist_codes, "klineData": {}})
                    results["klineSignals"]["klineData"][code] = value
                else:
                    results[key] = value
            except Exception:
                pass

    # 确保 klineSignals 存在
    if "klineSignals" not in results:
        results["klineSignals"] = {"watchlist": watchlist_codes, "klineData": {}}

    # 屏6 — 组合管理（当前仍合成，真实组合待 Phase 4 实施）
    positions = POSITIONS
    total_market_value = sum(p.get("marketValue", p.get("currentPrice", 0) * p.get("shares", 0)) for p in positions)
    total_pnl = sum(p.get("unrealizedPnl", 0) for p in positions)

    results["portfolio"] = {
        "totalAssets": ACCOUNT_METRICS["totalAssets"],
        "todayPnl": ACCOUNT_METRICS["todayPnl"],
        "todayPnlPct": ACCOUNT_METRICS["todayPnlPct"],
        "totalPnl": total_pnl,
        "positions": positions,
        "equityCurve": gen_equity_curve(),
        "dataSource": "mock",
    }

    # 元信息
    results["_meta"] = {
        "westockAvailable": dp.data_source_status()["westock_available"],
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }

    # 写入缓存，供后续请求直接命中
    DASHBOARD_CACHE["data"] = results
    DASHBOARD_CACHE["ts"] = time.time()
    return results
