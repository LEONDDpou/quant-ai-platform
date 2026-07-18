"""模拟盘交易系统 — 智能风控自动监控后台循环（企业级增强）。

风险监控循环：每隔 interval 秒遍历所有模拟账户，执行：
  1. 既有 scan_breaches（集中度 / 单日亏损 / 个股止损突破落库，去重）；
  2. 评估账户自定义规则（黑名单命中 / 行业集中度 / 最大回撤 / 杠杆等）；
  3. 触发的风险事件写入 paper_risk_events，供前端告警面板与 AI 复盘订阅。

风格与现有 _paper_ai_loop 一致：用 asyncio.to_thread 包裹同步服务调用，
单账户异常不阻断主循环，循环整体异常也不退出（持续守护）。
"""
import asyncio
import logging

from app.paper.services.risk_service import RiskService
from app.paper.repositories.account_repo import AccountRepository

logger = logging.getLogger("paper.risk_monitor")


async def risk_monitor_loop(interval: float = 60.0):
    """每 interval 秒自动扫描全部账户的实时风险与自定义规则。"""
    svc = RiskService()
    acct_repo = AccountRepository()
    logger.info("[risk_monitor] 智能风控自动监控循环启动，间隔 %.0fs", interval)
    while True:
        try:
            accounts = acct_repo.list_accounts()
            for acct in accounts:
                try:
                    # 1) 既有指标突破扫描（去重落库）
                    breaches = svc.scan_breaches(acct.id)
                    # 2) 自定义规则评估 + 去重落库
                    triggered = svc.evaluate_rules(acct.id)
                    if triggered:
                        logger.info("[risk_monitor] 账户 %d 触发 %d 条规则", acct.id, triggered)

                    # 3) 风险评分低时触发飞书告警（#P3）
                    try:
                        report = svc.get_risk_report(acct.id)
                        score = report.get("score", 100)
                        if score < 60:
                            from app.paper.services.alert_channel import get_alert_channel
                            alert = get_alert_channel()
                            if alert:
                                name = acct.name or f"账户{acct.id}"
                                alert.send(
                                    title=f"⚠️ 风险告警：{name}",
                                    message=f"**账户**: {name} (ID: {acct.id})\n"
                                            f"**风险评分**: {score}/100\n"
                                            f"**状态**: {report.get('status', 'unknown')}\n"
                                            f"**触发规则数**: {triggered}\n"
                                            f"**建议**: 请登录系统查看详情并处理",
                                    severity="critical" if score < 40 else "warning",
                                )
                    except Exception as e:
                        logger.debug("告警发送异常（不影响扫描）: %s", e)
                except Exception as e:  # 单账户失败不影响其他账户
                    logger.warning("[risk_monitor] 账户 %d 扫描失败: %s", acct.id, e)
        except Exception as e:
            logger.warning("[risk_monitor] 循环异常: %s", e)
        await asyncio.sleep(interval)
