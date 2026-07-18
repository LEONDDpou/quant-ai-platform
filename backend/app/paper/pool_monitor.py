"""模拟盘交易系统 — M179 股票池自动维护后台循环。

每 interval 秒遍历全部模拟账户执行一次自动维护：
- 自动同步板块/指数成分；
- 健康检测（停牌 / ST / 流动性）并按配置规则自动移除（锁定标的豁免）。
单账户异常不影响整体循环；网络/行情调用在线程中执行，避免阻塞事件循环。
"""
import asyncio
import logging

from app.paper.repositories.account_repo import AccountRepository
from app.paper.services.pool_service import PoolMaintenanceService

logger = logging.getLogger("paper.pool")


async def pool_maintenance_loop(interval: float = 300.0):
    """股票池自动维护后台循环。"""
    logger.info("[pool] auto maintenance loop started, interval=%.0fs", interval)
    svc = PoolMaintenanceService()
    acct_repo = AccountRepository()
    while True:
        try:
            accounts = acct_repo.list_accounts()
            for acct in accounts:
                try:
                    await asyncio.to_thread(svc.run_maintenance, acct.id)
                except Exception as e:  # noqa: BLE001
                    logger.warning("[pool] maintenance failed for account %s: %s", acct.id, e)
        except Exception as e:  # noqa: BLE001
            logger.warning("[pool] loop error: %s", e)
        await asyncio.sleep(interval)
