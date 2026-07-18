"""M4 持仓管理 — 冒烟测试。

验证 PositionService.get_summary / refresh_market_value_public 的聚合正确性。
直接对真实 ORM 建仓 + 成交，mock 行情返回确定性价格。
运行: DATABASE_URL="sqlite:///./tests/_m4_smoke_tmp.db" python tests/paper_m4_smoke.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///./tests/_m4_smoke_tmp.db"

# 在导入业务模块前，将行情 mock 为确定性价格
from app.paper.services import market_provider as MP  # noqa: E402

_PRICES = {
    "600519": {"price": 200.0, "prevClose": 190.0, "name": "贵州茅台"},
    "000001": {"price": 50.0, "prevClose": 52.0, "name": "中国平安"},
}

def _quote(code):
    return _PRICES.get(code, {"price": 100.0, "prevClose": 100.0, "name": code})

MP.market_provider.quote = _quote

from app.db.database import init_db, SessionLocal, engine  # noqa: E402
from app.paper.domain_models import (  # noqa: E402
    PaperAccount, PaperPosition, PaperTrade, Base,
)
from app.paper.repositories.account_repo import AccountRepository  # noqa: E402
from app.paper.services.position_service import PositionService  # noqa: E402

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")

# 干净库
Base.metadata.drop_all(engine)
init_db()

ACCT_ID = 1
with SessionLocal() as db:
    db.add(PaperAccount(
        id=ACCT_ID, name="demo", cash=100000.0,
        total_assets=100000.0, available_cash=100000.0,
    ))
    db.commit()

svc = PositionService()

# 建仓：600519 买 100 股 @200（成本200，现价200）；000001 买 200 股 @50（成本50，现价50）
with SessionLocal() as db:
    from datetime import datetime
    p1 = PaperPosition(account_id=ACCT_ID, code="600519", name="贵州茅台", industry="白酒",
                       shares=100, sellable_shares=100, cost_price=200.0, buy_price=200.0,
                       current_price=200.0, market_value=20000.0, pnl_amount=0.0, pnl_pct=0.0,
                       hold_days=2, position_ratio=0.0)
    p2 = PaperPosition(account_id=ACCT_ID, code="000001", name="中国平安", industry="金融",
                       shares=200, sellable_shares=200, cost_price=50.0, buy_price=50.0,
                       current_price=50.0, market_value=10000.0, pnl_amount=0.0, pnl_pct=0.0,
                       hold_days=2, position_ratio=0.0)
    db.add_all([p1, p2])
    db.commit()

# 账户总资产设为持仓市值 + 现金 = 30000 + 70000 = 100000（与初始一致）
with SessionLocal() as db:
    acct = db.get(PaperAccount, ACCT_ID)
    acct.cash = 70000.0
    acct.total_assets = 100000.0
    acct.available_cash = 70000.0
    db.commit()

print("M4 持仓汇总冒烟测试:")
# 1) 汇总基础字段
s = svc.get_summary(ACCT_ID)
check("持仓数=2", s["positionCount"] == 2, s["positionCount"])
check("总市值=30000", abs(s["totalMarketValue"] - 30000.0) < 1e-6, s["totalMarketValue"])
check("总成本=30000", abs(s["totalCost"] - 30000.0) < 1e-6, s["totalCost"])
# 600519: (200-200)*100=0 ; 000001: (50-50)*200=0 → 浮动盈亏=0
check("浮动盈亏=0", abs(s["unrealizedPnl"]) < 1e-6, s["unrealizedPnl"])
# 当日: 600519 (200-190)*100=1000 ; 000001 (50-52)*200=-400 → 600
check("当日盈亏=600", abs(s["todayPnl"] - 600.0) < 1e-6, s["todayPnl"])
# 集中度相对总资产(=100000，含现金70000+持仓30000)：20000/100000=20%，30000/100000=30%
check("最大单一占比≈20", abs(s["maxPositionRatio"] - 20.0) < 0.1, s["maxPositionRatio"])
check("前三大≈30", abs(s["top3Ratio"] - 30.0) < 0.1, s["top3Ratio"])

# 2) 行业分布（白酒 20000 + 金融 10000 → 66.67% / 33.33%）
ind = {d["industry"]: d["ratio"] for d in s["industryDistribution"]}
check("行业=白酒/金融", set(ind.keys()) == {"白酒", "金融"}, ind)
check("白酒占比≈66.67", abs(ind["白酒"] - 66.67) < 0.1, ind.get("白酒"))
check("金融占比≈33.33", abs(ind["金融"] - 33.33) < 0.1, ind.get("金融"))

# 3) 已实现盈亏（注入一笔卖出成交，成本200 卖@210 100股 费10 → 实现=(210-200)*100-10=990）
with SessionLocal() as db:
    db.add(PaperTrade(account_id=ACCT_ID, order_id=0, code="600519", name="贵州茅台",
                      direction="sell", price=210.0, quantity=100, amount=21000.0, fee=10.0,
                      realized_pnl=990.0, trade_time=datetime.now()))
    db.commit()
s2 = svc.get_summary(ACCT_ID)
check("已实现盈亏=990", abs(s2["realizedPnl"] - 990.0) < 1e-6, s2["realizedPnl"])
check("总盈亏=990", abs(s2["totalPnl"] - 990.0) < 1e-6, s2["totalPnl"])

# 4) refresh 用行情刷新 current_price：600519→200, 000001→50（与建仓一致，市值不变）
refreshed = svc.refresh_market_value_public(ACCT_ID)
check("refresh 返回 2 条持仓", len(refreshed) == 2, len(refreshed))
check("refresh 后 600519 现价=200", abs(refreshed[0].currentPrice - 200.0) < 1e-6, refreshed[0].currentPrice)

print(f"\n结果: PASS={PASS} FAIL={FAIL}")
if FAIL > 0:
    raise SystemExit(1)
print("✅ M4 持仓管理冒烟测试全部通过")
