"""AI 每日复盘自动生成循环（#186）。

每小时检查一次，对每个活跃账户在交易日生成复盘（当日尚未生成则触发）。
"""
import asyncio
import logging

from app.paper.services.daily_review_service import DailyReviewService
from app.paper.repositories.account_repo import AccountRepository

logger = logging.getLogger("paper.daily_review")


async def daily_review_loop(interval: float = 3600.0):
    """每隔 interval 秒检查全账户并生成当日复盘（如尚未生成）。"""
    svc = DailyReviewService()
    acct_repo = AccountRepository()
    while True:
        try:
            accounts = acct_repo.list_accounts()
            for acct in accounts:
                try:
                    if acct.status != "active":
                        continue
                    latest = svc.get_latest(acct.id)
                    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
                    if latest and latest.date == today:
                        continue  # 今日已生成
                    svc.generate_review(acct.id)
                    logger.info("已生成账户 %d 的 %s 复盘", acct.id, today)
                except Exception as e:
                    logger.warning("账户 %d 复盘失败: %s", acct.id, e)
        except Exception as e:
            logger.error("复盘循环异常: %s", e)
        await asyncio.sleep(interval)
