#!/usr/bin/env python3
"""M6 资金与收益曲线 / 统计中心 — 冒烟测试。

验证：
1. 统计核心：合成权益曲线（含人为回撤）+ 合成平仓成交 → 最大回撤 / 夏普 / 胜率 / 盈亏比；
2. refresh_statistics 写回账户绩效字段（max_drawdown / sharpe_ratio / win_rate / profit_loss_ratio）；
3. take_snapshot 按「账户+日期」幂等 upsert。
"""
import os
import sys
import tempfile

# 必须在导入任何 app 模块前设置临时数据库（database.py 在导入时即读取 DATABASE_URL）
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.name}"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import datetime

from app.db.database import init_db, SessionLocal
from app.db import models  # noqa: F401  确保主模型注册
from app.paper.domain_models import (
    User,
    PaperAccount,
    PaperTrade,
    PaperEquitySnapshot,
)
from app.paper.repositories.account_repo import AccountRepository
from app.paper.services.stats_service import StatsService

SVC = StatsService()
PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK]   {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}   {detail}")


def fresh_account(name, initial=1_000_000.0):
    return AccountRepository().create_account(1, name, initial)


# ========== 准备 ==========
init_db()
with SessionLocal() as db:
    if not db.query(User).filter_by(username="demo").first():
        u = User(username="demo", nickname="demo")
        db.add(u)
        db.commit()

# ---- 账户 A：合成权益曲线（升-回撤-新高）+ 合成平仓成交 ----
accA = fresh_account("M6-A", 1_000_000.0)
with SessionLocal() as db:
    for r in [
        PaperEquitySnapshot(account_id=accA.id, date="2026-07-01", total_assets=1_000_000, cash=1_000_000, position_value=0, daily_pnl=0, daily_pnl_pct=0, cumulative_pnl=0, cumulative_pnl_pct=0),
        PaperEquitySnapshot(account_id=accA.id, date="2026-07-02", total_assets=1_050_000, cash=1_050_000, position_value=0, daily_pnl=50_000, daily_pnl_pct=5.0, cumulative_pnl=50_000, cumulative_pnl_pct=5.0),
        PaperEquitySnapshot(account_id=accA.id, date="2026-07-03", total_assets=1_020_000, cash=1_020_000, position_value=0, daily_pnl=-30_000, daily_pnl_pct=-2.857, cumulative_pnl=20_000, cumulative_pnl_pct=2.0),
        PaperEquitySnapshot(account_id=accA.id, date="2026-07-04", total_assets=1_080_000, cash=1_080_000, position_value=0, daily_pnl=60_000, daily_pnl_pct=5.882, cumulative_pnl=80_000, cumulative_pnl_pct=8.0),
    ]:
        db.add(r)
    for t in [
        PaperTrade(account_id=accA.id, order_id=1, code="600519", name="贵州茅台", direction="sell", price=1700, quantity=100, amount=170000, fee=42.5, realized_pnl=1000, trade_time=datetime(2026, 7, 2)),
        PaperTrade(account_id=accA.id, order_id=2, code="000858", name="五粮液", direction="sell", price=150, quantity=100, amount=15000, fee=5, realized_pnl=2000, trade_time=datetime(2026, 7, 3)),
        PaperTrade(account_id=accA.id, order_id=3, code="601318", name="中国平安", direction="sell", price=50, quantity=100, amount=5000, fee=2.5, realized_pnl=-500, trade_time=datetime(2026, 7, 4)),
    ]:
        db.add(t)
    db.commit()

print("M6 统计核心 — 账户 A（合成权益曲线 + 合成平仓成交）")
statsA = SVC.get_statistics(accA.id)
check("快照数量 = 4", statsA["snapshotCount"] == 4, statsA["snapshotCount"])
check("累计收益率 = 8.0%", abs(statsA["cumulativePnlPct"] - 8.0) < 1e-6, statsA["cumulativePnlPct"])
check("最大回撤 ≈ 2.86%", abs(statsA["maxDrawdown"] - 2.8571) < 0.05, statsA["maxDrawdown"])
check("平仓笔数 = 3", statsA["tradeCount"] == 3, statsA["tradeCount"])
check("盈利平仓 = 2", statsA["winCount"] == 2, statsA["winCount"])
check("亏损平仓 = 1", statsA["lossCount"] == 1, statsA["lossCount"])
check("胜率 ≈ 66.67%", abs(statsA["winRate"] - 66.6667) < 0.05, statsA["winRate"])
check("盈亏比 = 3.0", abs(statsA["profitLossRatio"] - 3.0) < 1e-6, statsA["profitLossRatio"])
check("平均盈利 = 1500", abs(statsA["avgWin"] - 1500) < 1e-6, statsA["avgWin"])
check("平均亏损 = 500", abs(statsA["avgLoss"] - 500) < 1e-6, statsA["avgLoss"])
check("夏普为有限浮点", isinstance(statsA["sharpeRatio"], float), statsA["sharpeRatio"])

curve = SVC.get_equity_curve(accA.id)
check("收益曲线长度 = 4", len(curve) == 4, len(curve))
check("收益曲线按日期升序", curve[0]["date"] < curve[-1]["date"], curve[0]["date"])

# ---- 账户 B：验证 refresh 写回账户绩效字段 ----
accB = fresh_account("M6-B", 1_000_000.0)
with SessionLocal() as db:
    db.add(PaperTrade(account_id=accB.id, order_id=10, code="600519", name="贵州茅台", direction="sell", price=1700, quantity=100, amount=170000, fee=42.5, realized_pnl=3000, trade_time=datetime(2026, 7, 2)))
    db.add(PaperTrade(account_id=accB.id, order_id=11, code="000858", name="五粮液", direction="sell", price=150, quantity=100, amount=15000, fee=5, realized_pnl=-1000, trade_time=datetime(2026, 7, 3)))
    db.commit()

print("M6 写回账户字段 — 账户 B（refresh_statistics）")
statsB = SVC.refresh_statistics(accB.id)
acctB = AccountRepository().get_account(accB.id)
check("账户 win_rate 写回 = 50%", abs(acctB.win_rate - 50.0) < 1e-6, acctB.win_rate)
check("账户 profit_loss_ratio 写回 = 3.0", abs(acctB.profit_loss_ratio - 3.0) < 1e-6, acctB.profit_loss_ratio)
check("账户 max_drawdown 写回(浮点)", isinstance(acctB.max_drawdown, float), acctB.max_drawdown)
check("refresh 返回胜率 = 50%", abs(statsB["winRate"] - 50.0) < 1e-6, statsB["winRate"])
check("无持仓→最大回撤 = 0（基线=今日，扁平）", acctB.max_drawdown == 0.0, acctB.max_drawdown)
check("无持仓→夏普 = 0", statsB["sharpeRatio"] == 0.0, statsB["sharpeRatio"])

# ---- take_snapshot 幂等 ----
print("M6 快照幂等 — 账户 B")
s1 = SVC.take_snapshot(accB.id, "2026-07-10")
s2 = SVC.take_snapshot(accB.id, "2026-07-10")
check("同日期 upsert 唯一", s1.id == s2.id, f"{s1.id} vs {s2.id}")

print(f"\n结果：PASS={PASS}  FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
