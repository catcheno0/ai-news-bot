import os
import unittest
from unittest.mock import Mock, patch

from src.notifiers.wechat_official_notifier import WeChatOfficialNotifier


class WeChatOfficialNotifierTests(unittest.TestCase):
    def test_send_posts_template_message_with_digest_page_url(self):
        token_response = Mock()
        token_response.raise_for_status = Mock()
        token_response.json.return_value = {"access_token": "access-token", "expires_in": 7200}
        send_response = Mock()
        send_response.raise_for_status = Mock()
        send_response.json.return_value = {"errcode": 0, "errmsg": "ok", "msgid": 123}

        with patch.dict(
            os.environ,
            {
                "WECHAT_OFFICIAL_APP_ID": "app-id",
                "WECHAT_OFFICIAL_APP_SECRET": "app-secret",
                "WECHAT_OFFICIAL_OPENID": "openid-1",
                "WECHAT_OFFICIAL_TEMPLATE_ID": "template-1",
            },
            clear=True,
        ):
            with patch(
                "src.notifiers.wechat_official_notifier.requests.get",
                return_value=token_response,
            ) as get:
                with patch(
                    "src.notifiers.wechat_official_notifier.requests.post",
                    return_value=send_response,
                ) as post:
                    notifier = WeChatOfficialNotifier()

                    sent = notifier.send(
                        (
                            "# Today AI News\n\n"
                            "- [OpenAI](https://openai.com/news) released a model update."
                        ),
                        title="AI News Digest - 2026-08-02 [ZH]",
                        additional_data={"page_url": "https://news.my-ai-news.top/latest.html"},
                        language="zh",
                    )

        self.assertTrue(sent)
        get.assert_called_once()
        self.assertIn("appid=app-id", get.call_args.args[0])
        self.assertIn("secret=app-secret", get.call_args.args[0])

        post.assert_called_once()
        self.assertIn("access_token=access-token", post.call_args.args[0])
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["touser"], "openid-1")
        self.assertEqual(payload["template_id"], "template-1")
        self.assertEqual(payload["url"], "https://news.my-ai-news.top/latest.html")
        self.assertEqual(payload["data"]["keyword1"]["value"], "AI News Digest - 2026-08-02 [ZH]")
        self.assertIn("OpenAI", payload["data"]["keyword3"]["value"])
        self.assertLessEqual(len(payload["data"]["keyword3"]["value"]), 120)

    def test_send_without_required_settings_does_not_call_wechat(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.notifiers.wechat_official_notifier.requests.get") as get:
                with patch("src.notifiers.wechat_official_notifier.requests.post") as post:
                    notifier = WeChatOfficialNotifier()
                    sent = notifier.send("digest")

        self.assertFalse(sent)
        get.assert_not_called()
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
