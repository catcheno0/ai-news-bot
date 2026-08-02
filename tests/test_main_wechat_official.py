import unittest
from unittest.mock import Mock, patch

import main as app_main


class MainWeChatOfficialTests(unittest.TestCase):
    def test_main_sends_digest_page_url_to_wechat_official_notifier(self):
        config = Mock()
        config.log_level = "INFO"
        config.log_format = "%(message)s"
        config.ai_response_languages = ["zh"]
        config.llm_provider = "deepseek"
        config.llm_model = "deepseek-chat"
        config.llm_api_key = "test-key"
        config.enable_web_search = False
        config.strict_verification = True
        config.notification_methods = ["wechat_official"]
        config.max_items_per_source = 1
        config.stage1_prompt_template = "stage 1"
        config.stage2_prompt_template = "stage 2"
        config.verification_fail_policy = "skip"
        config.min_verified_items = 1
        config.max_articles_to_verify = 5
        config.news_max_age_hours = 96
        config.pages_enabled = True
        config.pages_output_dir = "public"
        config.pages_site_url = "https://news.my-ai-news.top"

        generator = Mock()
        generator.generate_news_digest_from_sources.return_value = "# AI Daily"

        publication = Mock()
        publication.latest_url = "https://news.my-ai-news.top/latest.html"
        publication.latest_path = "public/latest.html"

        publisher = Mock()
        publisher.publish.return_value = publication

        notifier = Mock()
        notifier.send.return_value = True

        with patch.object(app_main, "Config", return_value=config):
            with patch.object(app_main, "NewsGenerator", return_value=generator):
                with patch.object(app_main, "setup_logger", return_value=Mock()):
                    with patch.object(app_main, "DigestPagePublisher", return_value=publisher):
                        with patch.object(app_main, "WeChatOfficialNotifier", return_value=notifier):
                            with patch.object(app_main, "PushPlusNotifier") as pushplus:
                                exit_code = app_main.main()

        self.assertEqual(exit_code, 0)
        pushplus.assert_not_called()
        notifier.send.assert_called_once()
        kwargs = notifier.send.call_args.kwargs
        self.assertEqual(kwargs["language"], "zh")
        self.assertEqual(kwargs["additional_data"], {"page_url": "https://news.my-ai-news.top/latest.html"})
        self.assertIn("Full digest: https://news.my-ai-news.top/latest.html", notifier.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
