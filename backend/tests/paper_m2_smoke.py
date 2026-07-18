"""M2 冒烟测试 — 验证行情系统（实时行情/五档/K线/资金流向/板块/指数/WS 状态）。

运行（在 backend/ 目录下）：
    python tests/paper_m2_smoke.py

说明：
- 本沙箱无外网，MarketProvider 自动回退模拟数据（dataSource="mock"），
  但接口契约、字段完整性与取值范围均按真实行情标准校验；
- 部署环境有网时同一套代码会自动切换 data_source="akshare"。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.paper.services.market_provider import market_provider


def check_quote():
    q = market_provider.quote("600519")
    assert q["code"] == "600519"
    assert q["price"] > 0 and q["prevClose"] > 0
    assert q["high"] >= q["low"] >= 0
    assert -20 <= q["changePct"] <= 20, q["changePct"]
    assert q["amount"] >= 0
    assert q["dataSource"] in ("akshare", "mock")
    print(f"[OK] quote {q['code']} price={q['price']} chg%={q['changePct']} src={q['dataSource']}")


def check_order_book():
    ob = market_provider.order_book("600519")
    assert len(ob["bids"]) == 5 and len(ob["asks"]) == 5
    # 买档价格应严格递减（买一最高），卖档严格递增（卖一最低），且买一 < 卖一
    bids = [b["price"] for b in ob["bids"]]
    asks = [a["price"] for a in ob["asks"]]
    assert bids == sorted(bids, reverse=True)
    assert asks == sorted(asks)
    assert bids[0] < asks[0], (bids[0], asks[0])
    print(f"[OK] orderbook {ob['code']} bids={bids} asks={asks}")


def check_kline():
    for period in ["1m", "5m", "15m", "30m", "60m", "day", "week", "month"]:
        k = market_provider.kline("600519", period, 60)
        assert k["period"] == period
        assert len(k["points"]) > 0
        for p in k["points"]:
            assert p["high"] >= p["low"] >= 0
            assert p["high"] >= p["open"] and p["high"] >= p["close"]
        print(f"[OK] kline {period}: {len(k['points'])} points, src={k['dataSource']}")


def check_capital_flow():
    cf = market_provider.capital_flow("600519")
    assert cf["code"] == "600519"
    # 主力净流入 = 超大单 + 大单
    assert abs(cf["mainInflow"] - (cf["superLarge"] + cf["large"])) < 1.0
    print(f"[OK] capital-flow {cf['code']} main={cf['mainInflow']} src={cf['dataSource']}")


def check_sectors():
    for kind in ("industry", "concept"):
        secs = market_provider.sectors(kind)
        assert len(secs) > 0
        for s in secs:
            assert -11 <= s["changePct"] <= 11
            assert s["name"]
        print(f"[OK] sectors {kind}: {len(secs)} boards, top={secs[0]['name']} {secs[0]['changePct']}%")


def check_indices_and_status():
    idx = market_provider.indices()
    assert isinstance(idx, list)
    print(f"[OK] indices: {len(idx)} items")
    st = market_provider.status()
    assert "mode" in st and "akshareAvailable" in st and "networkReachable" in st
    print(f"[OK] status: {st}")


def main():
    check_quote()
    check_order_book()
    check_kline()
    check_capital_flow()
    check_sectors()
    check_indices_and_status()
    print("\n✅ M2 行情系统冒烟测试全部通过（dataSource 可能为 mock，符合沙箱预期）")


if __name__ == "__main__":
    main()
