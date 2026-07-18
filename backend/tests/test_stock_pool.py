"""模拟盘交易系统 — 股票池自动维护单元测试（无服务依赖，内存 SQLite）。

覆盖：标的 CRUD / 配置默认与更新 / 板块自动同步新增 / 健康检测判定 /
自动移除（含锁定豁免）。网络相关调用以桩对象隔离，保证确定性。

运行：cd backend && PYTHONPATH=. python tests/test_stock_pool.py
"""
import os
import tempfile
import unittest

# 必须在导入 app 任何模块前固定数据库连接为临时文件 SQLite，避免污染生产库
_TMP_DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

from app.db.database import init_db, SessionLocal  # noqa: E402
from app.paper.domain_models import PaperAccount, PaperPoolConfig  # noqa: E402
from app.paper.services import pool_service as _ps  # noqa: E402
from app.paper.services.pool_service import PoolMaintenanceService  # noqa: E402
from app.paper.schemas import PoolItemRequest, PoolConfigRequest  # noqa: E402


class _StubProvider:
    """隔离市场行情的网络调用，按 code 返回确定性行情（可配置 ST 名称）。"""

    def __init__(self, st_code: str = ""):
        self.st_code = st_code

    def quote(self, code: str) -> dict:
        name = "*ST测试股" if code == self.st_code else "测试股"
        return {"code": code, "name": name, "turnover": 2.0, "dataSource": "mock"}


class TestStockPool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with SessionLocal() as db:
            acct = PaperAccount(
                name="股票池测试账户",
                initial_capital=1_000_000.0,
                cash=1_000_000.0,
                total_assets=1_000_000.0,
            )
            db.add(acct)
            db.commit()
            db.refresh(acct)
            cls.account_id = acct.id

    def _svc(self, st_code: str = "") -> PoolMaintenanceService:
        svc = PoolMaintenanceService()
        svc.market_provider = _StubProvider(st_code)  # 桩：隔离网络
        return svc

    # ———————————————————— 标的 CRUD ————————————————————
    def test_item_crud(self):
        svc = self._svc()
        # 新增
        it = svc.add_item(self.account_id, PoolItemRequest(code="600519", name="贵州茅台", category="核心仓"))
        self.assertEqual(it.code, "600519")
        # 重复添加应抛错
        with self.assertRaises(Exception):
            svc.add_item(self.account_id, PoolItemRequest(code="600519"))
        # 更新（锁定 + 分组）
        upd = svc.update_item(it.id, category="观察", pinned=True)
        self.assertTrue(upd.pinned)
        self.assertEqual(upd.category, "观察")
        # 列表包含该标的
        self.assertTrue(any(x.code == "600519" for x in svc.list_items(self.account_id)))
        # 移除
        self.assertTrue(svc.remove_item(it.id))
        self.assertFalse(any(x.code == "600519" for x in svc.list_items(self.account_id)))

    # ———————————————————— 配置默认与更新 ————————————————————
    def test_config_default_and_upsert(self):
        svc = self._svc()
        default = svc.get_config(self.account_id)
        self.assertFalse(default.autoSync)
        self.assertTrue(default.removeSt)
        self.assertEqual(default.syncSource, "manual")

        upd = svc.upsert_config(
            self.account_id,
            PoolConfigRequest(autoSync=True, syncSource="sector", syncName="白酒",
                              removeSuspended=True, removeSt=True, removeIlliquid=True,
                              minTurnover=0.5, maxSize=10),
        )
        self.assertTrue(upd.autoSync)
        self.assertEqual(upd.syncName, "白酒")
        self.assertEqual(upd.maxSize, 10)
        # 再次读取应持久化
        again = svc.get_config(self.account_id)
        self.assertEqual(again.syncName, "白酒")
        self.assertEqual(again.minTurnover, 0.5)

    # ———————————————————— 板块自动同步新增 ————————————————————
    def test_sync_adds_constituents(self):
        # 强制走内置已知板块映射，避免真实网络
        _ps._try_akshare = lambda: None
        svc = self._svc()
        svc.upsert_config(
            self.account_id,
            PoolConfigRequest(autoSync=True, syncSource="sector", syncName="白酒"),
        )
        res = svc.run_maintenance(self.account_id)
        # 白酒映射含 5 只成分
        self.assertGreaterEqual(res.added, 5)
        codes = {x.code for x in svc.list_items(self.account_id)}
        self.assertIn("600519", codes)
        self.assertIn("000858", codes)

    # ———————————————————— 健康检测判定 ————————————————————
    def test_health_detection(self):
        svc = self._svc()
        cfg = PaperPoolConfig(account_id=self.account_id, min_turnover=1.0)  # 默认 ORM 配置
        # 无行情 → 停牌
        self.assertEqual(svc._detect_health("X", None, cfg), "suspended")
        # ST 名称（真实源）→ st
        st_quote = {"name": "*ST某某", "turnover": 1.0, "dataSource": "akshare"}
        self.assertEqual(svc._detect_health("X", st_quote, cfg), "st")
        # 真实源 + 换手率低于阈值 → illiquid
        ill_quote = {"name": "正常股", "turnover": 0.3, "dataSource": "akshare"}
        self.assertEqual(svc._detect_health("X", ill_quote, cfg), "illiquid")
        # 真实源 + 换手率充足 → ok
        ok_quote = {"name": "正常股", "turnover": 5.0, "dataSource": "akshare"}
        self.assertEqual(svc._detect_health("X", ok_quote, cfg), "ok")
        # 模拟源不判定流动性 → ok
        mock_quote = {"name": "正常股", "turnover": 0.01, "dataSource": "mock"}
        self.assertEqual(svc._detect_health("X", mock_quote, cfg), "ok")

    # ———————————————————— 自动移除 + 锁定豁免 ————————————————————
    def test_auto_remove_st_and_pin_skip(self):
        svc = self._svc(st_code="000001")  # 该 code 行情返回 ST 名称
        svc.upsert_config(
            self.account_id,
            PoolConfigRequest(autoSync=False, removeSt=True),  # 仅测移除，关闭同步
        )
        # 非锁定 ST 标的 → 应被自动移除
        svc.add_item(self.account_id, PoolItemRequest(code="000001"))
        res = svc.run_maintenance(self.account_id)
        self.assertGreaterEqual(res.removed, 1)
        self.assertEqual(len(svc.list_items(self.account_id)), 0)

        # 锁定 ST 标的 → 跳过移除
        svc.add_item(self.account_id, PoolItemRequest(code="000001", pinned=True))
        res2 = svc.run_maintenance(self.account_id)
        self.assertGreaterEqual(res2.skippedPinned, 1)
        self.assertEqual(res2.removed, 0)
        self.assertEqual(len(svc.list_items(self.account_id)), 1)


if __name__ == "__main__":
    unittest.main()
