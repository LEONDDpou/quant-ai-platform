"""M3 冒烟测试 — 验证订单系统与撮合引擎（A股规则）。

运行（在 backend/ 目录下）：
    python tests/paper_m3_smoke.py

为确定性与速度，本测试：
- 强制行情走 mock（patch _try_akshare → None），避免外网探测；
- 绕过交易时段校验（patch is_trading_time → True）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import init_db, SessionLocal
from app.paper.schemas import CreateAccountRequest, CreateOrderRequest
from app.paper.services.account_service import AccountService
from app.paper.services.order_service import OrderService
from app.paper.domain_models import PaperAccount, PaperPosition, PaperOrder, PaperTrade
from app.paper import trading_rules as R
from app.paper.services import market_provider as MP

# —— 测试桩：强制 mock 行情 + 绕过交易时段 ——
MP._try_akshare = lambda: None
R.is_trading_time = lambda dt=None: True


def fresh_account():
    svc = AccountService()
    a = svc.create_account(CreateAccountRequest(
        name="M3测试账户", initialCapital=1_000_000, preset="100万", username="demo"))
    return a.id


def get_acct(db, aid):
    return db.get(PaperAccount, aid)


def get_pos(db, aid, code):
    return db.query(PaperPosition).filter(
        PaperPosition.account_id == aid, PaperPosition.code == code).first()


def get_trades(db, aid):
    return db.query(PaperTrade).filter(PaperTrade.account_id == aid).all()


def main():
    init_db()
    svc = OrderService()
    aid = fresh_account()
    print(f"[OK] 创建账户 id={aid}")

    code = "600519"
    q = MP.market_provider.quote(code)
    px = q["price"]
    print(f"[INFO] {code} mock 现价={px}")

    # —— 1) 限价买入（委托价略高于市价 → 触发后按市价成交，价格改进）——
    buy_limit = round(px * 1.02, 2)
    before = get_acct(SessionLocal(), aid)
    o = svc.create_order(CreateOrderRequest(
        accountId=aid, code=code, name=q["name"], direction="buy",
        orderType="limit", price=buy_limit, quantity=1000))[0]
    assert o.status == "filled", f"预期成交, 实际 {o.status}"
    after = get_acct(SessionLocal(), aid)
    pos = get_pos(SessionLocal(), aid, code)
    trades = get_trades(SessionLocal(), aid)
    assert pos and pos.shares == 1000, f"持仓应为1000, 实际 {pos.shares if pos else None}"
    assert pos.cost_price == px, f"成本价应=成交价 {px}, 实际 {pos.cost_price}"
    assert pos.sellable_shares == 0, f"T+1: 当日买入可卖应为0, 实际 {pos.sellable_shares}"  # T+1
    # 现金 = 初始 - (金额+费)，冻结应释放
    expect_cash = round(before.cash - (px * 1000 + o.fee), 2)
    assert abs(after.cash - expect_cash) < 0.01, f"现金 {after.cash} vs {expect_cash}"
    assert after.frozen_cash == 0.0, f"成交后冻结应为0, 实际 {after.frozen_cash}"
    assert len(trades) == 1 and trades[0].quantity == 1000
    print(f"[OK] 限价买入成交: 价={o.avgFillPrice} 费={o.fee} 现金={after.cash:.2f} 可卖={pos.sellable_shares}")

    # —— 2) T+1 当日不可卖 ——
    sell_px = round(px * 0.99, 2)  # 落在涨跌停区间内且低于市价（保证可成交）
    try:
        svc.create_order(CreateOrderRequest(
            accountId=aid, code=code, name=q["name"], direction="sell",
            orderType="limit", price=sell_px, quantity=1000))[0]
        raise AssertionError("同日卖出应被 T+1 拦截")
    except Exception as e:
        assert "可卖数量不足" in str(e) or "INSUFFICIENT" in str(e), str(e)
    print("[OK] T+1 当日卖出被拦截（可卖数量不足）")

    # —— 3) 日终滚动后卖出 ——
    svc.position_svc.rollover_day(aid)
    pos = get_pos(SessionLocal(), aid, code)
    assert pos.sellable_shares == 1000, f"滚动后可卖应=1000, 实际 {pos.sellable_shares}"
    o2 = svc.create_order(CreateOrderRequest(
        accountId=aid, code=code, name=q["name"], direction="sell",
        orderType="limit", price=sell_px, quantity=1000))[0]
    assert o2.status == "filled", f"卖出应成交, 实际 {o2.status}"
    pos2 = get_pos(SessionLocal(), aid, code)
    assert pos2 is None, "清仓后持仓应删除"
    trades2 = get_trades(SessionLocal(), aid)
    assert any(t.realized_pnl != 0 for t in trades2), "卖出应产生实现盈亏"
    print(f"[OK] 滚动后卖出成交: 实现盈亏={trades2[-1].realized_pnl:.2f}, 持仓已清")

    # —— 4) 市价买入 ——
    o3 = svc.create_order(CreateOrderRequest(
        accountId=aid, code="000001", direction="buy", orderType="market", quantity=100))[0]
    assert o3.status in ("filled", "partial"), o3.status
    print(f"[OK] 市价买入: {o3.status} qty={o3.filledQuantity}")

    # —— 5) 止损条件单（未触发 → pending）——
    # 先做日终滚动，使 000001 持仓变为可卖，再挂止损卖单
    svc.position_svc.rollover_day(aid)
    o4 = svc.create_order(CreateOrderRequest(
        accountId=aid, code="000001", direction="sell", orderType="stop_loss",
        triggerPrice=0.01, quantity=100))[0]
    assert o4.status == "pending", f"未触发止损应 pending, 实际 {o4.status}"
    print(f"[OK] 止损条件单创建: {o4.status} (触发价={o4.triggerPrice})")

    # —— 6) 分批建仓（3 笔）——
    px2 = MP.market_provider.quote("300750")["price"]
    batch_list = svc.create_order(CreateOrderRequest(
        accountId=aid, code="300750", direction="buy", orderType="limit",
        price=round(px2 * 1.02, 2), quantity=900, tranches=3))
    assert len(batch_list) == 3, f"分批应3笔, 实际 {len(batch_list)}"
    assert sum(o.quantity for o in batch_list) == 900
    print(f"[OK] 分批建仓: 生成 {len(batch_list)} 笔, 合计 {sum(o.quantity for o in batch_list)} 股")

    # —— 7) 网格单（低价区间，全部为买挂单，低于中枢不成交 → pending）——
    grid = svc.create_order(CreateOrderRequest(
        accountId=aid, code="601318", direction="buy", orderType="grid", quantity=100,
        gridLower=1.0, gridUpper=5.0, gridStep=2.0, gridQtyPer=100))
    assert len(grid) >= 2, f"网格应生成多笔, 实际 {len(grid)}"
    print(f"[OK] 网格单: 生成 {len(grid)} 笔子限价单")

    # —— 8) 撤单 ——
    pending = [o for o in grid if o.status == "pending"]
    if pending:
        cancelled = svc.cancel_order(aid, pending[0].id)
        assert cancelled.status == "cancelled"
        print(f"[OK] 撤单: order#{pending[0].id} → cancelled")

    # —— 9) 整手校验 ——
    try:
        svc.create_order(CreateOrderRequest(
            accountId=aid, code="600519", direction="buy", orderType="limit",
            price=99999.0, quantity=150))[0]
        raise AssertionError("非整手应被拦截")
    except Exception as e:
        assert "整数倍" in str(e), str(e)
    print("[OK] 非整手(150股)委托被拦截")

    print("\n✅ M3 冒烟测试全部通过")


if __name__ == "__main__":
    main()
