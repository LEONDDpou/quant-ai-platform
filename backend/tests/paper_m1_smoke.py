"""M1 冒烟测试 — 验证账户系统可创建 / 查询 / 列表。

运行（在 backend/ 目录下）：
    python tests/paper_m1_smoke.py
依赖 .env 中的 DATABASE_URL，默认 sqlite:///./quant.db。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import init_db
from app.paper.schemas import CreateAccountRequest
from app.paper.services.account_service import AccountService


def main():
    init_db()  # 确保模拟盘表已建
    svc = AccountService()

    # 1) 创建账户（预设 100万）
    a = svc.create_account(
        CreateAccountRequest(name="测试账户A", initialCapital=1_000_000, preset="100万", username="demo")
    )
    assert a.totalAssets == 1_000_000.0, a.totalAssets
    assert a.availableCash == 1_000_000.0
    print(f"[OK] 创建账户 id={a.id} name={a.name} totalAssets={a.totalAssets}")

    # 2) 自定义资金（500万）
    b = svc.create_account(
        CreateAccountRequest(name="测试账户B", initialCapital=5_000_000, preset="500万", username="demo")
    )
    assert b.totalAssets == 5_000_000.0
    print(f"[OK] 创建账户 id={b.id} name={b.name} totalAssets={b.totalAssets}")

    # 3) 详情 + 指标
    detail = svc.get_account(a.id)
    metrics = svc.get_metrics(a.id)
    assert detail.totalPnl == 0.0 and detail.totalPnlPct == 0.0
    assert metrics.positionRatio == 0.0
    print(f"[OK] 详情 id={detail.id} totalPnl={detail.totalPnl} pnlPct={detail.totalPnlPct}%")

    # 4) 列表
    lst = svc.list_accounts(username="demo")
    assert len(lst) >= 2
    print(f"[OK] 列表返回 {len(lst)} 个账户（demo）")

    print("\n✅ M1 冒烟测试全部通过")


if __name__ == "__main__":
    main()
