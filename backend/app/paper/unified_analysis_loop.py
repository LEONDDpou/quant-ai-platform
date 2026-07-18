"""统一分析循环 —— 合并研究员研究 + 每日复盘复盘为单个后台守护。

每隔 3600 秒执行一次：
1. 研究员规则研究（ResearcherAgentService.run_research 规则模式）
2. 每日复盘生成（DailyReviewService.generate_review 对每个活跃账户）

异常隔离：单账户失败不中断循环。
"""
import asyncio
import logging

from app.paper.repositories.account_repo import AccountRepository
from app.paper.services.daily_review_service import DailyReviewService

logger = logging.getLogger("paper.unified_analysis")


async def unified_analysis_loop(interval: float = 3600.0):
    """统一分析循环：研究 + 复盘。"""
    acct_repo = AccountRepository()
    review_svc = DailyReviewService()
    while True:
        try:
            accounts = acct_repo.list_accounts()
            # 1) 研究员研究（规则模式，全局宇宙）
            try:
                from app.paper.services.research_service import ResearcherAgentService
                from app.paper.schemas import RunResearchRequest
                research_svc = ResearcherAgentService()
                research_svc.run_research(RunResearchRequest(
                    accountId=None, universe=[], useLlm=False, maxIdeas=2,
                ))
                logger.info("统一分析：研究员研究完成")
            except Exception as e:
                logger.warning("统一分析：研究员研究异常: %s", e)

            # 2) 每日复盘（逐个活跃账户）
            for acct in accounts:
                try:
                    if acct.status != "active":
                        continue
                    import datetime
                    today = datetime.datetime.now().strftime("%Y-%m-%d")
                    latest = review_svc.get_latest(acct.id)
                    if latest and latest.date == today:
                        continue
                    review_svc.generate_review(acct.id)
                    logger.info("统一分析：已生成账户 %d 的 %s 复盘", acct.id, today)
                except Exception as e:
                    logger.warning("统一分析：账户 %d 复盘异常: %s", acct.id, e)
        except Exception as e:
            logger.error("统一分析循环异常: %s", e)
        await asyncio.sleep(interval)
