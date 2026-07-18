"""告警通道抽象 + 飞书 Webhook 实现（#P3）。

支持插件式扩展：实现 AlertChannel.send 即可注册新通道。
"""
import json
import logging
import os
from typing import Optional
from urllib import request

logger = logging.getLogger("paper.alert")


class AlertChannel:
    """告警通道基类。"""

    def send(self, title: str, message: str, severity: str = "info") -> bool:
        """发送告警。返回是否成功。"""
        raise NotImplementedError


class FeishuAlert(AlertChannel):
    """飞书机器人 Webhook 告警通道。

    配置环境变量 FEISHU_WEBHOOK_URL。
    消息格式参考飞书自定义机器人文档：
    https://open.feishu.cn/document/client-docs/bot-v2/add-custom-bot
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL", "")

    def send(self, title: str, message: str, severity: str = "info") -> bool:
        if not self.webhook_url:
            logger.debug("FEISHU_WEBHOOK_URL 未配置，跳过飞书告警")
            return False

        color_map = {"info": "blue", "warning": "orange", "critical": "red"}
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color_map.get(severity, "blue"),
                },
                "elements": [
                    {"tag": "markdown", "content": message},
                    {"tag": "note", "elements": [
                        {"tag": "plain_text", "content": f"severity: {severity} | 量化交易系统告警"},
                    ]},
                ],
            },
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = request.Request(
                self.webhook_url, data=data,
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                ok = "success" in body and (body.startswith("{") or body.startswith("["))
                if not ok:
                    logger.warning("飞书告警返回异常: %s", body[:200])
                return ok
        except Exception as e:
            logger.warning("飞书告警发送失败: %s", e)
            return False


# 单例（懒加载，由环境变量控制是否启用）
_feishu: Optional[FeishuAlert] = None


def get_alert_channel() -> Optional[AlertChannel]:
    """获取当前可用的告警通道（已配置 Webhook 则返回 FeishuAlert，否则 None）。"""
    global _feishu
    url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not url:
        return None
    if _feishu is None:
        _feishu = FeishuAlert(url)
    return _feishu
