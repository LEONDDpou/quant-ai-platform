"""M5 风险控制冒烟测试。

覆盖：
1) 默认配置返回平台默认值；
2) 单票集中度越限 → 前置风控拦截（evaluate_pre_trade 返回 False）；
3) 单笔金额越限 → 拦截；
4) 单日亏损触限 → 拦截新建多头；
5) 阈值内正常买入 → 通过；
6) metrics 状态判定（ok / breach）；
7) scan_breaches 记录事件 + 去重（第二次扫描不重复落库）；
8) 个股止损破线 → scan 记录 STOP_LOSS_BREACH。

运行（临时库，不污染 quant.db）：
    DATABASE_URL="sqlite:///./tests/_m5_smoke_tmp.db" \
        <venv>/python tests/paper_m5_smoke.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///./tests/_m5_smoke_tmp.db"

# —— 行情 mock（确定性）——
import app.paper.services.market_provider as MP  # noqa: E402

_PRICES = {"600519": 200.0, "000001": 50.0}
_PREV = {"600519": 210.0, "000001": 52.0}  # 600519 昨收 210、现价 200 → 当日亏损
_NAMES = {"600519": "贵州茅台", "000001": "中国平安"}


def _quote(code):
    return {"price": _PRICES.get(code, 100.0), "prevClose": _PREV.get(code, 100.0),
            "name": _NAMES.get(code, code)}


MP.market_provider.quote = _quote

from app.db.database import init_db, SessionLocal  # noqa: E402
from app.paper.domain_models import PaperAccount, PaperPosition  # noqa: E402
from app.paper.repositories.account_repo import AccountRepository  # noqa: E402
from app.paper.services.risk_service import RiskService  # noqa: E402

ACCT = 9001
passed = 0


def check(name, cond, extra=""):
    global passed
    status = "OK " if cond else "FAIL"
    if cond:
        passed += 1
    print(f"[{status}] {name} {extra}")


def reset():
    init_db()
    with SessionLocal() as db:
        db.query(PaperPosition).filter(PaperPosition.account_id == ACCT).delete()
        acct = db.query(PaperAccount).filter(PaperAccount.id == ACCT).first()
        if not acct:
            acct = PaperAccount(id=ACCT, name="risk-test", cash=1_000_000.0,
                                total_assets=1_000_000.0, available_cash=1_000_000.0)
            db.add(acct)
        acct.cash = 1_000_000.0
        acct.total_assets = 1_000_000.0
        acct.position_value = 0.0
        db.commit()


def make_position(code, shares, price):
    with SessionLocal() as db:
        pos = PaperPosition(account_id=ACCT, code=code, name=_NAMES.get(code, code),
                            shares=shares, sellable_shares=shares, cost_price=price,
                            buy_price=price, current_price=price, market_value=shares * price,
                            pnl_amount=0.0, pnl_pct=0.0, hold_days=1, position_ratio=0.0)
        db.add(pos)
        db.commit()


def clear_events():
    from app.paper.domain_models import PaperRiskEvent
    with SessionLocal() as db:
        db.query(PaperRiskEvent).filter(PaperRiskEvent.account_id == ACCT).delete()
        db.commit()


svc = RiskService()

# 1) 默认配置
reset()
cfg = svc.get_config(ACCT)
check("默认单票上限=0.5", abs(cfg["maxPositionRatio"] - 0.5) < 1e-9)
check("默认单日亏损=50000", cfg["maxDailyLoss"] == 50000.0)

# 2) 单票集中度越限 → 拦截
reset()
make_position("600519", 1000, 200.0)  # 市值 200000 = 20% 总资产
svc.upsert_config(ACCT, __import__("app.paper.schemas", fromlist=["RiskConfigRequest"])
                  .RiskConfigRequest(maxPositionRatio=0.10))
ok, vios = svc.evaluate_pre_trade(ACCT, "600519", "buy", "limit", 200.0, 100)
check("集中度越限被拦截", (not ok) and any("仓位占比" in v for v in vios), str(vios))

# 3) 单笔金额越限 → 拦截
reset()
make_position("600519", 1000, 200.0)
svc.upsert_config(ACCT, __import__("app.paper.schemas", fromlist=["RiskConfigRequest"])
                  .RiskConfigRequest(maxSingleAmount=50000.0))
ok, vios = svc.evaluate_pre_trade(ACCT, "600519", "buy", "limit", 200.0, 300)  # 60000 > 50000
check("单笔金额越限被拦截", (not ok) and any("单笔委托金额" in v for v in vios), str(vios))

# 4) 单日亏损触限 → 拦截
reset()
make_position("600519", 1000, 200.0)  # 当日亏损 (200-210)*1000 = -10000
svc.upsert_config(ACCT, __import__("app.paper.schemas", fromlist=["RiskConfigRequest"])
                  .RiskConfigRequest(maxDailyLoss=5000.0))
ok, vios = svc.evaluate_pre_trade(ACCT, "000001", "buy", "limit", 50.0, 100)
check("单日亏损触限拦截多头", (not ok) and any("单日亏损" in v for v in vios), str(vios))

# 5) 阈值内正常买入 → 通过
reset()
make_position("600519", 1000, 200.0)
svc.upsert_config(ACCT, __import__("app.paper.schemas", fromlist=["RiskConfigRequest"])
                  .RiskConfigRequest())  # 恢复默认
ok, vios = svc.evaluate_pre_trade(ACCT, "000001", "buy", "limit", 50.0, 100)  # 5000 元，远低上限
check("阈值内买入通过", ok, str(vios))

# 6) metrics 状态判定
reset()
make_position("600519", 1000, 200.0)
svc.upsert_config(ACCT, __import__("app.paper.schemas", fromlist=["RiskConfigRequest"])
                  .RiskConfigRequest())
m = svc.metrics(ACCT)
check("metrics 总仓位≈20%", abs(m["totalPositionRatio"] - 0.20) < 0.02, f"ratio={m['totalPositionRatio']:.3f}")
check("metrics 最大单票≈20%", abs(m["maxPositionRatio"] - 0.20) < 0.02, f"max={m['maxPositionRatio']:.3f}")
check("metrics 综合状态 ok", m["overallStatus"] == "ok", m["overallStatus"])
# 设严格阈值后应为 breach
svc.upsert_config(ACCT, __import__("app.paper.schemas", fromlist=["RiskConfigRequest"])
                  .RiskConfigRequest(maxPositionRatio=0.10))
m2 = svc.metrics(ACCT)
check("严格阈值后集中度 breach", m2["concentrationStatus"] == "breach", m2["concentrationStatus"])

# 7) scan 记录 + 去重
reset()
clear_events()
make_position("600519", 1000, 200.0)
svc.upsert_config(ACCT, __import__("app.paper.schemas", fromlist=["RiskConfigRequest"])
                  .RiskConfigRequest(maxPositionRatio=0.10))
n1 = svc.scan_breaches(ACCT)
n2 = svc.scan_breaches(ACCT)  # 24h 内同类型去重
check("首次扫描记录事件>0", n1 > 0, f"n1={n1}")
check("二次扫描去重(记录=0)", n2 == 0, f"n2={n2}")

# 8) 个股止损破线 → STOP_LOSS_BREACH
reset()
clear_events()
# 持仓成本 200，现价 150 → 浮亏 25% > 止损线 20%
make_position("600519", 1000, 200.0)
with SessionLocal() as db:
    pos = db.query(PaperPosition).filter(PaperPosition.account_id == ACCT,
                                         PaperPosition.code == "600519").first()
    pos.current_price = 150.0
    pos.market_value = 150000.0
    pos.pnl_amount = -50000.0
    pos.pnl_pct = -25.0
    db.commit()
svc.upsert_config(ACCT, __import__("app.paper.schemas", fromlist=["RiskConfigRequest"])
                  .RiskConfigRequest(stopLossRatio=0.20))
n = svc.scan_breaches(ACCT)
events = svc.list_events(ACCT)
has_sl = any(e.event_type == "STOP_LOSS_BREACH" for e in events)
check("止损破线触发 STOP_LOSS_BREACH", n > 0 and has_sl, f"n={n}")

print(f"\n✅ M5 风险控制冒烟测试通过 {passed}/13")
assert passed == 13, f"仅通过 {passed}/13"
