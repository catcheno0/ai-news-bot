import unittest
from unittest.mock import Mock, patch

import main as app_main


class MainPagesTests(unittest.TestCase):
    def test_main_publishes_digest_page_and_appends_link_to_pushplus(self):
        config = Mock()
        config.log_level = "INFO"
        config.log_format = "%(message)s"
        config.ai_response_languages = ["zh"]
        config.llm_provider = "deepseek"
        config.llm_model = "deepseek-chat"
        config.llm_api_key = "test-key"
        config.enable_web_search = False
        config.strict_verification = True
        config.notification_methods = ["pushplus"]
        config.max_items_per_source = 1
        config.stage1_prompt_template = "stage 1"
        config.stage2_prompt_template = "stage 2"
        config.verification_fail_policy = "skip"
        config.min_verified_items = 1
        config.max_articles_to_verify = 5
        config.pages_enabled = True
        config.pages_output_dir = "public"
        config.pages_site_url = "https://news.my-ai-news.top"

        generator = Mock()
        generator.generate_news_digest_from_sources.return_value = "# AI Daily"

        publication = Mock()
        publication.latest_url = "https://news.my-ai-news.top/latest.html"

        publisher = Mock()
        publisher.publish.return_value = publication

        notifier = Mock()
        notifier.send.return_value = True

        with patch.object(app_main, "Config", return_value=config):
            with patch.object(app_main, "NewsGenerator", return_value=generator):
                with patch.object(app_main, "setup_logger", return_value=Mock()):
                    with patch.object(app_main, "DigestPagePublisher", return_value=publisher):
                        with patch.object(app_main, "PushPlusNotifier", return_value=notifier):
                            exit_code = app_main.main()

        self.assertEqual(exit_code, 0)
        publisher.publish.assert_called_once()
        publish_kwargs = publisher.publish.call_args.kwargs
        self.assertEqual(publish_kwargs["language"], "zh")
        self.assertTrue(publish_kwargs["primary"])

        sent_content = notifier.send.call_args.args[0]
        self.assertIn("# AI Daily", sent_content)
        self.assertIn("Full digest: https://news.my-ai-news.top/latest.html", sent_content)


