"""机构维度数据聚合服务 — 统一聚合机构维度的多源数据，减少分析工具重复查询。

聚合内容：
  - 龙虎榜机构席位明细（含净买入、占成交比）
  - 主力资金流向（今日 + 5日 + 20日）
  - 机构调研记录（近期调研频率、评级分布）
  - 板块资金偏好（机构资金在行业间的分布）
  - 北向资金 / 沪股通 / 深股通净流向

缓存策略：各子模块独立 TTL（15-120s），聚合结果总体 30s。
"""

import time
import concurrent.futures as _cf
from app.services.westock_client import run_table, WeStockError
from app.services.market_dynamics_service import (
    get_lhb, get_capital_flow, get_sector_rankings, _to_float,
)


CACHE: dict[str, tuple[float, object]] = {}
CACHE_TTL = 30


def _cached(key: str, fetcher, ttl: int = CACHE_TTL):
    now = time.time()
    if key in CACHE:
        ts, val = CACHE[key]
        if now - ts < ttl:
            return val
    val = fetcher()
    CACHE[key] = (now, val)
    return val


# ============================================================
# 北向资金（沪股通 + 深股通）
# ============================================================
def get_northbound_flow() -> dict:
    """获取北向资金净流入数据。"""

    def _fetch():
        try:
            rows = run_table(["asfund", "sh000001"], timeout=15)
            if not rows:
                return {"today": 0.0, "todayDesc": "—", "recent": []}
            r = rows[0]
            nb_val = _to_float(r.get("NorthFlow", 0))
            return {
                "today": nb_val,
                "todayDesc": f"{nb_val/1e8:+.1f}亿" if abs(nb_val) > 0 else "净流出",
                "recent": [],  # 暂取当日值
            }
        except Exception:
            return {"today": 0.0, "todayDesc": "—", "recent": []}

    return _cached("northbound", _fetch, ttl=60)


# ============================================================
# 机构持仓汇总（基于龙虎榜 + 资金流向的推导）
# ============================================================
def get_institution_positions() -> list[dict]:
    """聚合机构在当前市场的持仓特征：重仓行业、净买入个股 Top 10。"""

    def _fetch():
        lhb = get_lhb(15)
        sectors = get_sector_rankings(10)

        # 从龙虎榜中提取机构净买入最多的个股
        top_buys = sorted(
            [e for e in lhb if not (e.get("netBuyAmt") or "—").startswith("-")],
            key=lambda e: _to_float(
                (e.get("netBuyAmt") or "0万")
                .replace("亿", "e8").replace("万", "e4").replace("—", "0"),
                0,
            ),
            reverse=True,
        )[:8]

        # 行业资金偏好：按板块涨跌推断
        hot_sectors = sorted(sectors, key=lambda s: s["chg5d"], reverse=True)[:6]
        cold_sectors = sorted(sectors, key=lambda s: s["chg5d"])[:3]

        return {
            "topInstitutionBuys": [
                {
                    "code": e["code"],
                    "name": e["name"],
                    "netBuyAmt": e["netBuyAmt"],
                    "buyRatio": e.get("buyRatio", "—"),
                    "instSeats": e.get("instSeats", 0),
                }
                for e in top_buys
            ],
            "hotSectors": [
                {"name": s["name"], "chg5d": s["chg5d"]} for s in hot_sectors
            ],
            "coldSectors": [
                {"name": s["name"], "chg5d": s["chg5d"]} for s in cold_sectors
            ],
        }

    return _cached("inst_positions", _fetch, ttl=60)


# ============================================================
# 机构交易活跃度指标
# ============================================================
def get_institution_activity() -> dict:
    """计算机构交易活跃度综合指标。"""

    def _fetch():
        lhb = get_lhb(15)
        cf = get_capital_flow()

        # 龙虎榜活跃度
        total_buy = sum(
            _to_float(
                (e.get("instBuyAmt") or "0")
                .replace("亿", "e8").replace("万", "e4").replace("—", "0"),
                0,
            )
            for e in lhb
        )
        lhb_count = len(lhb)

        # 主力净流入方向
        main_direction = "流入" if cf.get("mainNetFlow", 0) > 0 else "流出"
        main_intensity = abs(cf.get("mainNetFlow", 0))

        # 综合评分 (0-100)
        # 龙虎榜活跃度分（max 15 只 = 100）
        lhb_score = min(lhb_count / 15 * 50, 50)
        # 主力金额分（100 亿 = 满分 50）
        flow_score = min(main_intensity / 1e10 * 50, 50)
        total_score = round(lhb_score + flow_score, 1)

        return {
            "score": total_score,
            "level": "活跃" if total_score >= 60 else ("温和" if total_score >= 30 else "冷清"),
            "lhbCount": lhb_count,
            "lhbTotalBuy": total_buy,
            "mainDirection": main_direction,
            "mainIntensity": main_intensity,
            "mainFlow5d": cf.get("mainNetFlow5d", 0),
            "mainFlow20d": cf.get("mainNetFlow20d", 0),
        }

    return _cached("inst_activity", _fetch, ttl=45)


# ============================================================
# 聚合全部机构数据
# ============================================================
def get_institution_aggregate() -> dict:
    """返回机构维度的完整聚合数据，供分析工具统一调用。

    单次请求替代原有的多次独立查询，减少分析页面的网络开销。
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # 并行获取子模块
    results: dict = {}

    def _lhb():
        results["lhb"] = get_lhb(15)

    def _capital():
        results["capitalFlow"] = get_capital_flow()

    def _northbound():
        results["northbound"] = get_northbound_flow()

    def _positions():
        results["institutionPositions"] = get_institution_positions()

    def _activity():
        results["institutionActivity"] = get_institution_activity()

    with _cf.ThreadPoolExecutor(max_workers=5) as ex:
        futs = [
            ex.submit(f) for f in (_lhb, _capital, _northbound, _positions, _activity)
        ]
        for fut in _cf.as_completed(futs):
            try:
                fut.result()
            except Exception:
                pass

    return {
        "timestamp": timestamp,
        **results,
    }


def clear_cache() -> None:
    CACHE.clear()
