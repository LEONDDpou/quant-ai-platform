"""飞书告警通道单元测试。"""
import os
import unittest
from unittest import mock


class TestAlertChannel(unittest.TestCase):
    def test_feishu_alert_send(self):
        """飞书告警应能正确构造 payload 并发送。"""
        from app.paper.services.alert_channel import FeishuAlert
        alert = FeishuAlert("https://open.feishu.cn/open-apis/bot/v2/hook/test")

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = b'{"StatusCode":0,"StatusMessage":"success"}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            ok = alert.send("测试告警", "这是一条测试消息", severity="warning")
            self.assertTrue(ok)

            # 验证 payload 结构
            call_args = mock_urlopen.call_args
            self.assertIsNotNone(call_args)
            import json
            body = json.loads(call_args[0][0].data.decode("utf-8"))
            self.assertEqual(body["msg_type"], "interactive")
            self.assertEqual(body["card"]["header"]["title"]["content"], "测试告警")
            self.assertEqual(body["card"]["header"]["template"], "orange")

    def test_no_webhook_returns_false(self):
        """未配置 Webhook URL 时 send 应静默返回 False。"""
        from app.paper.services.alert_channel import FeishuAlert
        alert = FeishuAlert("")
        ok = alert.send("测试", "消息")
        self.assertFalse(ok)

    def test_get_alert_channel_no_env(self):
        """未设置环境变量时 get_alert_channel 应返回 None。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            from app.paper.services.alert_channel import get_alert_channel
            ch = get_alert_channel()
            self.assertIsNone(ch)

    def test_get_alert_channel_with_env(self):
        """设置 FEISHU_WEBHOOK_URL 时应返回 FeishuAlert 实例。"""
        with mock.patch.dict(os.environ, {"FEISHU_WEBHOOK_URL": "https://open.feishu.cn/hook/test"}):
            from app.paper.services.alert_channel import get_alert_channel
            ch = get_alert_channel()
            self.assertIsNotNone(ch)
            from app.paper.services.alert_channel import FeishuAlert
            self.assertIsInstance(ch, FeishuAlert)


if __name__ == "__main__":
    unittest.main(verbosity=2)
