import os
import unittest
from unittest.mock import Mock, patch

from src.notifiers.wechat_push_lite_notifier import WeChatPushLiteNotifier


class WeChatPushLiteNotifierTests(unittest.TestCase):
    def test_send_posts_digest_to_push_lite_backend(self):
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {"status": "sent", "message_id": 123}

        with patch.dict(
            os.environ,
            {
                "WECHAT_PUSH_LITE_URL": "http://127.0.0.1:8000/api/send",
                "WECHAT_PUSH_LITE_TOKEN": "secret-token",
            },
            clear=True,
        ):
            with patch(
                "src.notifiers.wechat_push_lite_notifier.requests.post",
                return_value=response,
            ) as post:
                notifier = WeChatPushLiteNotifier()

                sent = notifier.send("# Today\nAI news", language="zh")

        self.assertTrue(sent)
        post.assert_called_once()
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertEqual(url, "http://127.0.0.1:8000/api/send")
        self.assertEqual(kwargs["json"]["content"], "# Today\nAI news")
        self.assertEqual(kwargs["json"]["template"], "markdown")
        self.assertIn("[ZH]", kwargs["json"]["title"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-token")
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")

    def test_send_can_reuse_push_api_token(self):
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {"status": "sent", "message_id": 456}

        with patch.dict(os.environ, {"PUSH_API_TOKEN": "shared-token"}, clear=True):
            with patch(
                "src.notifiers.wechat_push_lite_notifier.requests.post",
                return_value=response,
            ) as post:
                notifier = WeChatPushLiteNotifier(url="http://localhost:8000/api/send")

                sent = notifier.send("digest", title="Custom title")

        self.assertTrue(sent)
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer shared-token")
        self.assertEqual(post.call_args.kwargs["json"]["title"], "Custom title")

    def test_send_without_token_does_not_call_backend(self):
        with patch.dict(
            os.environ,
            {"WECHAT_PUSH_LITE_URL": "http://127.0.0.1:8000/api/send"},
            clear=True,
        ):
            with patch("src.notifiers.wechat_push_lite_notifier.requests.post") as post:
                notifier = WeChatPushLiteNotifier()

                sent = notifier.send("digest")

        self.assertFalse(sent)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
