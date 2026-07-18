"""模拟盘交易系统 — 幂等数据库迁移。

问题背景：SQLAlchemy 的 ``Base.metadata.create_all`` 只会「创建不存在的表」，
不会为已存在的表「追加新列」。M3 给 ``paper_orders`` 新增了 4 个列
（parent_id / trigger_price / params / remark），旧表（M1/M2 已建）不会自动获得。

本模块在 ``init_db`` 后调用，按 PRAGMA 探测缺失列并用 ``ALTER TABLE ADD COLUMN``
补齐（SQLite 支持，且列均为可空，不影响既有数据，如演示账户）。可重复执行，安全幂等。
"""
from sqlalchemy import inspect, text

from app.db.database import engine


def migrate_paper_schema() -> None:
    """为已存在的模拟盘表补齐 M3 / M7 新增列。新安装的库由 create_all 直接建好，本函数无副作用。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("paper_orders"):
            return
        existing = {c["name"] for c in insp.get_columns("paper_orders")}
        # (列名, SQL 类型) —— SQLite 端 JSON 统一用 TEXT 存储（与 ORM 编译一致）
        target = [
            ("parent_id", "INTEGER"),
            ("trigger_price", "FLOAT"),
            ("params", "TEXT"),
            ("remark", "VARCHAR(200)"),
        ]
        with engine.begin() as conn:
            for col, ddl in target:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE paper_orders ADD COLUMN {col} {ddl}"))

        # —— M7：paper_positions 补齐止损/止盈价列（0 表示未设置）——
        if insp.has_table("paper_positions"):
            pos_existing = {c["name"] for c in insp.get_columns("paper_positions")}
            pos_target = [
                ("stop_loss_price", "FLOAT"),
                ("take_profit_price", "FLOAT"),
            ]
            for col, ddl in pos_target:
                if col not in pos_existing:
                    with engine.begin() as conn2:
                        conn2.execute(text(f"ALTER TABLE paper_positions ADD COLUMN {col} {ddl}"))

        # —— M8：backtest_runs 补齐 params(JSON→TEXT) 列 ——
        if insp.has_table("backtest_runs"):
            bt_existing = {c["name"] for c in insp.get_columns("backtest_runs")}
            if "params" not in bt_existing:
                with engine.begin() as conn3:
                    conn3.execute(text("ALTER TABLE backtest_runs ADD COLUMN params TEXT"))
            # —— M181：backtest_runs 补齐 mode 列（factor / event）——
            if "mode" not in bt_existing:
                with engine.begin() as conn4:
                    conn4.execute(text("ALTER TABLE backtest_runs ADD COLUMN mode VARCHAR(20) DEFAULT 'factor'"))

        # —— M179：watchlists 补齐股票池自动维护扩展列 ——
        if insp.has_table("watchlists"):
            wl_existing = {c["name"] for c in insp.get_columns("watchlists")}
            wl_target = [
                ("pinned", "BOOLEAN"),
                ("category", "VARCHAR(30)"),
                ("health", "VARCHAR(20)"),
                ("last_checked", "TIMESTAMP"),
                ("source", "VARCHAR(30)"),
            ]
            for col, ddl in wl_target:
                if col not in wl_existing:
                    with engine.begin() as conn4:
                        conn4.execute(text(f"ALTER TABLE watchlists ADD COLUMN {col} {ddl}"))
    except Exception as e:  # 迁移失败不应阻塞启动
        print(f"[migrate] paper schema migration skipped: {e}")
