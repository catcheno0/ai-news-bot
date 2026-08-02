from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

from src.config import Config
from src.news import fetcher as fetcher_module
from src.news.fetcher import NewsFetcher
from src.news.generator import NewsGenerator


class NewsQualityTests(unittest.TestCase):
    def setUp(self):
        self.fetcher = NewsFetcher()

    def test_strict_mode_uses_only_primary_and_research_feeds(self):
        expected_sources = {
            "OpenAI News",
            "Google AI Blog",
            "Google DeepMind Blog",
            "Google Research Blog",
            "HuggingFace Blog",
            "NVIDIA Deep Learning Blog",
            "AWS Machine Learning Blog",
            "GitHub Blog AI",
            "arXiv AI",
            "arXiv Machine Learning",
            "arXiv Computer Vision",
            "arXiv NLP",
        }
        disabled_sources = {
            "Anthropic Blog",
            "Microsoft AI Blog",
            "Hacker News",
            "Reddit r/LocalLLaMA",
            "Google News AI (CN)",
            "Google News LLM (CN)",
            "Sina Tech (新浪科技)",
            "JiQiZhiXin (机器之心)",
        }

        self.assertTrue(expected_sources.issubset(self.fetcher.rss_feeds))
        self.assertFalse(disabled_sources & self.fetcher.rss_feeds.keys())
        self.assertTrue(all(url.startswith("https://") for url in self.fetcher.rss_feeds.values()))
        self.assertEqual(self.fetcher.chinese_feeds, {})
        self.assertEqual(set(self.fetcher.rss_feeds), set(self.fetcher.source_tiers))
        self.assertTrue(set(self.fetcher.source_tiers.values()) <= {"official", "research"})

    def test_fetch_recent_news_deduplicates_titles_and_keeps_official_source(self):
        now = datetime.now(timezone.utc).isoformat()
        self.fetcher.rss_feeds = {
            "OpenAI News": "https://example.com/openai.xml",
            "arXiv AI": "https://example.com/arxiv.xml",
        }
        self.fetcher.source_tiers = {
            "OpenAI News": "official",
            "arXiv AI": "research",
        }
        self.fetcher.fetch_rss_feed = Mock(side_effect=[
            [{"title": "Model release", "link": "https://example.com/openai", "description": "Official release", "published": now}],
            [{"title": "MODEL RELEASE", "link": "https://example.com/paper", "description": "Paper", "published": now}],
        ])

        news = self.fetcher.fetch_recent_news(language="en", max_items_per_source=1)

        self.assertEqual(len(news["international"]), 1)
        self.assertEqual(news["international"][0]["source"], "OpenAI News")
        self.assertEqual(news["international"][0]["source_tier"], "official")


    def test_fetch_rss_feed_keeps_atom_entries_with_empty_summary_text(self):
        response = Mock()
        response.content = b'<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n  <entry>\n    <title>DeepMind update</title>\n    <link href="https://deepmind.google/example" />\n    <summary></summary>\n    <updated>2026-07-30T00:00:00Z</updated>\n  </entry>\n</feed>'
        response.raise_for_status = Mock()

        with patch("src.news.fetcher.requests.get", return_value=response):
            items = self.fetcher.fetch_rss_feed("https://example.com/feed.xml", max_items=1)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["description"], "")

    def test_time_filter_discards_items_without_a_parseable_publication_time(self):
        now = datetime.now(timezone.utc).isoformat()
        items = [
            {"title": "Dated", "published": now},
            {"title": "Undated", "published": "not a date"},
        ]

        kept = self.fetcher._filter_by_time(items)

        self.assertEqual([item["title"] for item in kept], ["Dated"])



    def test_fetch_recent_news_uses_configured_max_age_window(self):
        now = datetime.now(timezone.utc)
        self.fetcher.rss_feeds = {"OpenAI News": "https://example.com/openai.xml"}
        self.fetcher.source_tiers = {"OpenAI News": "official"}
        self.fetcher.fetch_rss_feed = Mock(return_value=[
            {
                "title": "Within expanded window",
                "link": "https://openai.com/recent",
                "description": "Recent",
                "published": (now.replace(microsecond=0) - fetcher_module.timedelta(hours=72)).isoformat(),
            },
            {
                "title": "Too old",
                "link": "https://openai.com/old",
                "description": "Old",
                "published": (now.replace(microsecond=0) - fetcher_module.timedelta(hours=120)).isoformat(),
            },
        ])

        news = self.fetcher.fetch_recent_news(
            language="en",
            max_items_per_source=2,
            max_age_hours=96,
        )

        self.assertEqual([item["title"] for item in news["international"]], ["Within expanded window"])


    def test_config_exposes_strict_verification_settings(self):
        config = Config.__new__(Config)
        config.config_data = {
            "news": {
                "strict_verification": True,
                "verification_fail_policy": "skip",
                "min_verified_items": 8,
                "max_articles_to_verify": 40,
            }
        }

        self.assertTrue(config.strict_verification)
        self.assertEqual(config.verification_fail_policy, "skip")
        self.assertEqual(config.min_verified_items, 8)
        self.assertEqual(config.max_articles_to_verify, 40)

    def test_checked_in_config_allows_sparse_verified_daily_digest(self):
        config = Config("config.yaml")

        self.assertLessEqual(config.min_verified_items, 2)
        self.assertNotIn("Select exactly 15-20", config.stage1_prompt_template)
        self.assertIn("If fewer than 5 verified items are available", config.stage1_prompt_template)

    def test_checked_in_config_expands_verified_candidate_pool_without_lowering_source_tier(self):
        config = Config("config.yaml")

        self.assertEqual(config.max_items_per_source, 15)
        self.assertEqual(config.max_articles_to_verify, 80)
        self.assertEqual(config.news_max_age_hours, 96)
        self.assertIn("select 5-8", config.stage1_prompt_template.lower())
        self.assertTrue(config.strict_verification)
        self.assertEqual(config.verification_fail_policy, "skip")

    def test_article_verifier_marks_items_with_matching_source_domain_and_body(self):
        verifier_class = getattr(fetcher_module, "ArticleVerifier")
        verifier = verifier_class(
            source_domains={"OpenAI News": ["openai.com"]},
            min_text_chars=30,
            max_text_chars=200,
        )
        response = Mock()
        response.content = b"""<html><head><title>Model release</title></head><body><h1>Model release</h1><p>OpenAI released a model update with concrete details for developers.</p></body></html>"""
        response.raise_for_status = Mock()
        item = {
            "title": "Model release",
            "link": "https://openai.com/news/model-release",
            "description": "Short RSS summary",
            "published": "2026-07-30T00:00:00+00:00",
            "source": "OpenAI News",
            "source_tier": "official",
        }

        with patch("src.news.fetcher.requests.get", return_value=response):
            verified = verifier.verify_item(item)

        self.assertIsNotNone(verified)
        self.assertEqual(verified["verification_status"], "body_verified")
        self.assertIn("OpenAI released a model update", verified["verified_text"])

    def test_strict_verification_skips_items_that_fail_body_verification(self):
        now = datetime.now(timezone.utc).isoformat()
        self.fetcher.rss_feeds = {"OpenAI News": "https://example.com/openai.xml"}
        self.fetcher.source_tiers = {"OpenAI News": "official"}
        self.fetcher.fetch_rss_feed = Mock(return_value=[
            {"title": "Verified", "link": "https://openai.com/verified", "description": "One", "published": now},
            {"title": "Rejected", "link": "https://evil.example/rejected", "description": "Two", "published": now},
        ])
        self.fetcher.article_verifier = Mock()
        self.fetcher.article_verifier.verify_item.side_effect = [
            {"title": "Verified", "link": "https://openai.com/verified", "description": "One", "published": now, "source": "OpenAI News", "source_tier": "official", "verification_status": "body_verified", "verified_text": "Verified article body"},
            None,
        ]

        news = self.fetcher.fetch_recent_news(
            language="en",
            max_items_per_source=2,
            strict_verification=True,
            max_articles_to_verify=10,
        )

        self.assertEqual([item["title"] for item in news["international"]], ["Verified"])
        self.assertEqual(news["international"][0]["verification_status"], "body_verified")


    def test_strict_verification_round_robins_sources_before_limit(self):
        now = datetime.now(timezone.utc).isoformat()
        self.fetcher.rss_feeds = {
            "OpenAI News": "https://example.com/openai.xml",
            "Google AI Blog": "https://example.com/google.xml",
        }
        self.fetcher.source_tiers = {
            "OpenAI News": "official",
            "Google AI Blog": "official",
        }
        self.fetcher.fetch_rss_feed = Mock(side_effect=[
            [{"title": f"OpenAI {i}", "link": f"https://openai.com/{i}", "description": "", "published": now} for i in range(3)],
            [{"title": f"Google {i}", "link": f"https://blog.google/{i}", "description": "", "published": now} for i in range(3)],
        ])

        def verify(item):
            verified = dict(item)
            verified["verification_status"] = "body_verified"
            verified["verified_text"] = f"Body for {item['title']}"
            return verified

        self.fetcher.article_verifier = Mock()
        self.fetcher.article_verifier.verify_item.side_effect = verify

        news = self.fetcher.fetch_recent_news(
            language="en",
            max_items_per_source=3,
            strict_verification=True,
            max_articles_to_verify=2,
        )

        self.assertEqual([item["title"] for item in news["international"]], ["OpenAI 0", "Google 0"])

    def test_selection_input_contains_verified_article_text(self):
        generator = NewsGenerator.__new__(NewsGenerator)
        formatted, _ = generator._format_news_with_ids({
            "international": [{
                "title": "Official model release",
                "source": "OpenAI News",
                "source_tier": "official",
                "verification_status": "body_verified",
                "verified_text": "Original article body with details that should ground the summary.",
                "link": "https://openai.com/news/example",
                "description": "Release details",
                "published": "2026-07-30T00:00:00+00:00",
            }],
            "domestic": [],
        })

        self.assertIn("**Verification:** body_verified", formatted)
        self.assertIn("**Verified Article Text:** Original article body", formatted)

    def test_digest_verification_skips_unsupported_selected_items_and_regenerates(self):
        class FakeProvider:
            provider_name = "fake"
            model = "fake-model"

            def __init__(self):
                self.prompts = []
                self.responses = [
                    '["INT-1", "INT-2"]',
                    "Digest with unsupported item",
                    '{"passed": false, "unsupported_news_ids": ["INT-2"], "reason": "Unsupported claim"}',
                    "Verified digest only",
                    '{"passed": true, "unsupported_news_ids": [], "reason": "ok"}',
                ]

            def generate(self, messages, max_tokens=2000, **kwargs):
                self.prompts.append(messages[0]["content"])
                return self.responses.pop(0)

        generator = NewsGenerator.__new__(NewsGenerator)
        generator.provider = FakeProvider()
        generator.news_fetcher = Mock()
        generator.news_fetcher.fetch_recent_news.return_value = {
            "international": [
                {"title": "One", "source": "OpenAI News", "source_tier": "official", "verification_status": "body_verified", "verified_text": "Original text one", "link": "https://openai.com/one", "description": "One", "published": "2026-07-30T00:00:00+00:00"},
                {"title": "Two", "source": "OpenAI News", "source_tier": "official", "verification_status": "body_verified", "verified_text": "Original text two", "link": "https://openai.com/two", "description": "Two", "published": "2026-07-30T00:00:00+00:00"},
            ],
            "domestic": [],
        }
        generator.enable_web_search = False
        generator.search_tool = None

        digest = generator.generate_news_digest_from_sources(
            language="en",
            max_items_per_source=1,
            stage1_template="{formatted_news}\\nReturn JSON for {total_items} items.",
            stage2_template="Selected {count}\\n{selected_news}",
            strict_verification=True,
            verification_fail_policy="skip",
            min_verified_items=1,
            max_articles_to_verify=5,
            news_max_age_hours=96,
        )

        self.assertIn("Verified digest only", digest)
        self.assertEqual(generator.provider.prompts[3].count("### [INT-2]"), 0)
        generator.news_fetcher.fetch_recent_news.assert_called_once_with(
            language="en",
            max_items_per_source=1,
            strict_verification=True,
            max_articles_to_verify=5,
            max_age_hours=96,
        )

    def test_selection_respects_five_to_eight_target_without_padding_to_old_floor(self):
        class FakeProvider:
            provider_name = "fake"
            model = "fake-model"

            def __init__(self):
                self.prompts = []
                self.responses = [
                    '["INT-1", "INT-2", "INT-3", "INT-4", "INT-5"]',
                    "Digest for five items",
                ]

            def generate(self, messages, max_tokens=2000, **kwargs):
                self.prompts.append(messages[0]["content"])
                return self.responses.pop(0)

        generator = NewsGenerator.__new__(NewsGenerator)
        generator.provider = FakeProvider()
        generator.news_fetcher = Mock()
        generator.news_fetcher.fetch_recent_news.return_value = {
            "international": [
                {
                    "title": f"Item {idx}",
                    "source": "OpenAI News",
                    "source_tier": "official",
                    "verification_status": "body_verified",
                    "verified_text": f"Original text {idx}",
                    "link": f"https://openai.com/{idx}",
                    "description": f"Item {idx}",
                    "published": "2026-07-30T00:00:00+00:00",
                }
                for idx in range(1, 9)
            ],
            "domestic": [],
        }
        generator.enable_web_search = False
        generator.search_tool = None

        digest = generator.generate_news_digest_from_sources(
            language="en",
            max_items_per_source=1,
            stage1_template="{formatted_news}\nReturn 5 IDs from {total_items} items.",
            stage2_template="Selected {count}\n{selected_news}",
            strict_verification=False,
        )

        self.assertIn("Digest for five items", digest)
        self.assertIn("Selected 5", generator.provider.prompts[1])
        self.assertNotIn("### [INT-6]", generator.provider.prompts[1])


    def test_selection_input_contains_link_and_source_tier(self):
        generator = NewsGenerator.__new__(NewsGenerator)
        formatted, _ = generator._format_news_with_ids({
            "international": [{
                "title": "Official model release",
                "source": "OpenAI News",
                "source_tier": "official",
                "link": "https://openai.com/news/example",
                "description": "Release details",
                "published": "2026-07-30T00:00:00+00:00",
            }],
            "domestic": [],
        })

        self.assertIn("**Source Tier:** official", formatted)
        self.assertIn("**Link:** https://openai.com/news/example", formatted)


if __name__ == "__main__":
    unittest.main()
