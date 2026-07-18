"""研究员 Agent 后台自动研究循环（#182）。

周期性（默认每小时）对「默认观察宇宙」跑一次规则确定性研究，自动挖掘因子 +
生成策略想法并落库，形成「无人值守」的量化研究流。

设计要点（对齐既有后台循环风格）：
- 用 asyncio 任务启动，循环内用 asyncio.to_thread 包裹同步调用；
- 单账户/单次研究异常不中断循环；循环级异常也兜底继续；
- 仅规则模式（不依赖外网 LLM、零成本），适合定时批量研究；
- 默认宇宙使用平台观察池（与 llm_service.WATCHLIST 一致）。
"""
import asyncio
import logging

from app.paper.services.research_service import ResearcherAgentService, DEFAULT_UNIVERSE
from app.paper.schemas import RunResearchRequest

logger = logging.getLogger("paper.research_monitor")


async def researcher_loop(interval: float = 3600.0):
    """研究员 Agent 自动研究循环：每隔 interval 秒研究一次默认宇宙。"""
    logger.info("[研究员Agent] 自动研究循环启动，间隔 %.0f 秒", interval)
    svc = ResearcherAgentService()
    while True:
        try:
            # 规则模式、全局会话（account_id=None），默认宇宙
            req = RunResearchRequest(
                accountId=None,
                universe=list(DEFAULT_UNIVERSE),
                useLlm=False,
                maxIdeas=3,
            )
            result = await asyncio.to_thread(svc.run_research, req)
            logger.info(
                "[研究员Agent] 自动研究完成：会话#%s，因子 %d，策略 %d",
                result.session.id, result.factorCount, result.ideaCount,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("[研究员Agent] 本次自动研究失败（不影响循环）：%s", e)
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("[研究员Agent] 自动研究循环被取消")
            break
