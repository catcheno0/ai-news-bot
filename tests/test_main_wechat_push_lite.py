import unittest
from unittest.mock import Mock, patch

import main as app_main


class MainWeChatPushLiteTests(unittest.TestCase):
    def test_main_sends_digest_when_wechat_push_lite_is_enabled(self):
        config = Mock()
        config.log_level = "INFO"
        config.log_format = "%(message)s"
        config.ai_response_languages = ["zh"]
        config.llm_provider = "claude"
        config.llm_model = None
        config.llm_api_key = "test-key"
        config.enable_web_search = False
        config.strict_verification = True
        config.notification_methods = ["wechat_push_lite"]
        config.max_items_per_source = 1
        config.stage1_prompt_template = "stage 1"
        config.stage2_prompt_template = "stage 2"
        config.verification_fail_policy = "skip"
        config.min_verified_items = 1
        config.max_articles_to_verify = 5
        config.news_max_age_hours = 96
        config.pages_enabled = False
        config.pages_output_dir = "public"
        config.pages_site_url = ""

        generator = Mock()
        generator.generate_news_digest_from_sources.return_value = "# AI Daily"
        notifier = Mock()
        notifier.send.return_value = True

        with patch.object(app_main, "Config", return_value=config):
            with patch.object(app_main, "NewsGenerator", return_value=generator):
                with patch.object(app_main, "setup_logger", return_value=Mock()):
                    with patch.object(app_main, "WeChatPushLiteNotifier", return_value=notifier):
                        exit_code = app_main.main()

        self.assertEqual(exit_code, 0)
        notifier.send.assert_called_once_with("# AI Daily", language="zh")


if __name__ == "__main__":
    unittest.main()
