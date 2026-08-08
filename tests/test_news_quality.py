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

    def test_strict_mode_uses_tiered_sources_without_untrusted_domains(self):
        expected_sources = {
            "OpenAI News",
            "Google AI Blog",
            "Google DeepMind Blog",
            "Google Research Blog",
            "HuggingFace Blog",
            "NVIDIA Deep Learning Blog",
            "AWS Machine Learning Blog",
            "GitHub Blog AI",
            "PyTorch Blog",
            "TensorFlow Blog",
            "arXiv AI",
            "arXiv Machine Learning",
            "arXiv Computer Vision",
            "arXiv NLP",
            "BAIR Blog",
            "MIT AI News",
            "TechCrunch AI",
            "VentureBeat AI",
            "MIT Technology Review AI",
            "Hacker News AI",
            "Qwen Blog",
            "DeepSeek Releases",
            "Tencent Hunyuan Releases",
            "PaddlePaddle Releases",
            "MindSpore Releases",
            "InternLM Releases",
            "MiniCPM Releases",
            "arXiv China AI Models",
        }
        trusted_domestic_sources = {
            "Tencent WorkBuddy Changelog",
            "QbitAI",
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
        self.assertFalse(disabled_sources & self.fetcher.chinese_feeds.keys())
        self.assertTrue(all(url.startswith("https://") for url in self.fetcher.rss_feeds.values()))
        self.assertTrue(trusted_domestic_sources.issubset(
            set(self.fetcher.official_page_sources) | set(self.fetcher.chinese_feeds)
        ))
        configured_sources = (
            set(self.fetcher.rss_feeds)
            | set(self.fetcher.official_page_sources)
            | set(self.fetcher.chinese_feeds)
        )
        self.assertEqual(configured_sources, set(self.fetcher.source_tiers))
        self.assertEqual(configured_sources, set(self.fetcher.source_domains))
        self.assertTrue(set(self.fetcher.source_tiers.values()) <= {"official", "research", "editorial", "community"})
        self.assertEqual(self.fetcher.source_tiers["TechCrunch AI"], "editorial")
        self.assertEqual(self.fetcher.source_tiers["Hacker News AI"], "community")
        self.assertEqual(self.fetcher.source_tiers["Tencent WorkBuddy Changelog"], "official")
        self.assertEqual(self.fetcher.source_tiers["QbitAI"], "editorial")

    def test_workbuddy_changelog_page_parses_recent_release_items(self):
        html = """
        <h1>WorkBuddy \u66f4\u65b0\u65e5\u5fd7</h1>
        <h2>5.3.8 \u7248\u672c\u53d1\u5e03\uff082026-07-30\uff09</h2>
        <ul>
            <li>\u4f18\u5316 macOS \u6587\u4ef6\u7cfb\u7edf\uff0c\u4fee\u590d\u957f\u671f\u4f7f\u7528\u4e0b\u7684\u6027\u80fd\u95ee\u9898</li>
            <li>\u4fee\u590d\u4ea7\u54c1\u7d22\u5f15\u81a8\u80c0\u5bfc\u81f4\u5386\u53f2\u4efb\u52a1\u65e0\u6cd5\u6062\u590d\u7684\u95ee\u9898</li>
        </ul>
        """
        source = {
            "url": "https://www.workbuddy.cn/docs/workbuddy/Changelog",
            "title_prefix": "WorkBuddy",
        }

        items = self.fetcher._parse_official_page_updates(
            "Tencent WorkBuddy Changelog",
            source,
            html,
            max_items=3,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "Tencent WorkBuddy Changelog")
        self.assertEqual(items[0]["source_tier"], "official")
        self.assertEqual(items[0]["title"], "WorkBuddy 5.3.8 \u7248\u672c\u53d1\u5e03\uff082026-07-30\uff09")
        self.assertEqual(items[0]["link"], "https://www.workbuddy.cn/docs/workbuddy/Changelog")
        self.assertEqual(items[0]["published"], "2026-07-30T00:00:00+08:00")
        self.assertIn("\u4f18\u5316 macOS \u6587\u4ef6\u7cfb\u7edf", items[0]["description"])

    def test_community_source_only_accepts_primary_article_domains(self):
        verifier = fetcher_module.ArticleVerifier(self.fetcher.source_domains)

        self.assertTrue(
            verifier._is_allowed_source_link("Hacker News AI", "https://arxiv.org/abs/2601.00001")
        )
        self.assertTrue(
            verifier._is_allowed_source_link("Hacker News AI", "https://github.com/example/model")
        )
        self.assertFalse(
            verifier._is_allowed_source_link("Hacker News AI", "https://www.youtube.com/watch?v=example")
        )
        self.assertFalse(
            verifier._is_allowed_source_link("Hacker News AI", "https://random-blog.example/post")
        )

    def test_corroboration_metadata_marks_related_cross_tier_items(self):
        news_data = {
            "international": [
                {
                    "title": "OpenAI releases GPT-5 model for developers",
                    "source": "OpenAI News",
                    "source_tier": "official",
                    "link": "https://openai.com/news/gpt-5",
                    "description": "OpenAI releases GPT-5 model",
                },
                {
                    "title": "OpenAI launches GPT-5 developer model",
                    "source": "TechCrunch AI",
                    "source_tier": "editorial",
                    "link": "https://techcrunch.com/example",
                    "description": "TechCrunch reports on OpenAI's GPT-5 developer model",
                },
            ],
            "domestic": [],
        }

        annotated = self.fetcher._annotate_corroboration(news_data)

        official_item = annotated["international"][0]
        editorial_item = annotated["international"][1]
        self.assertEqual(official_item["selection_role"], "primary")
        self.assertEqual(editorial_item["selection_role"], "corroborated_primary")
        self.assertEqual(editorial_item["corroboration_score"], 1)
        self.assertEqual(editorial_item["supporting_sources"], ["OpenAI News"])

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
        self.assertIn("selection role", config.stage1_prompt_template.lower())
        self.assertIn("context_only", config.stage1_prompt_template)
        self.assertNotIn('Only select items with an "official" or "research" source tier', config.stage1_prompt_template)
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


    def test_selection_filters_context_only_items_and_falls_back_to_primary_sources(self):
        class FakeProvider:
            provider_name = "fake"
            model = "fake-model"

            def __init__(self):
                self.prompts = []
                self.responses = [
                    '["INT-2"]',
                    "Digest from fallback primary item",
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
                {
                    "title": "Official model release",
                    "source": "OpenAI News",
                    "source_tier": "official",
                    "selection_role": "primary",
                    "verification_status": "body_verified",
                    "verified_text": "Official source text",
                    "link": "https://openai.com/news/model",
                    "description": "Official release",
                    "published": "2026-07-30T00:00:00+00:00",
                },
                {
                    "title": "Forum rumor about a model",
                    "source": "Hacker News AI",
                    "source_tier": "community",
                    "selection_role": "context_only",
                    "corroboration_score": 0,
                    "supporting_sources": [],
                    "verification_status": "body_verified",
                    "verified_text": "Forum discussion text",
                    "link": "https://news.ycombinator.com/item?id=1",
                    "description": "Forum discussion",
                    "published": "2026-07-30T00:00:00+00:00",
                },
            ],
            "domestic": [],
        }
        generator.enable_web_search = False
        generator.search_tool = None

        digest = generator.generate_news_digest_from_sources(
            language="en",
            max_items_per_source=1,
            stage1_template="{formatted_news}\nReturn JSON for {total_items} items.",
            stage2_template="Selected {count}\n{selected_news}",
            strict_verification=True,
            verification_fail_policy="skip",
            min_verified_items=1,
            max_articles_to_verify=5,
        )

        self.assertIn("Digest from fallback primary item", digest)
        self.assertIn("Selected 1", generator.provider.prompts[1])
        self.assertIn("### [INT-1]", generator.provider.prompts[1])
        self.assertNotIn("### [INT-2]", generator.provider.prompts[1])

    def test_selection_input_contains_corroboration_metadata(self):
        generator = NewsGenerator.__new__(NewsGenerator)
        formatted, _ = generator._format_news_with_ids({
            "international": [{
                "title": "OpenAI model report",
                "source": "TechCrunch AI",
                "source_tier": "editorial",
                "selection_role": "corroborated_primary",
                "corroboration_score": 2,
                "supporting_sources": ["OpenAI News", "Hacker News AI"],
                "supporting_source_tiers": ["official", "community"],
                "link": "https://techcrunch.com/example",
                "description": "Report details",
                "published": "2026-07-30T00:00:00+00:00",
            }],
            "domestic": [],
        })

        self.assertIn("**Selection Role:** corroborated_primary", formatted)
        self.assertIn("**Corroboration:** score=2", formatted)
        self.assertIn("OpenAI News", formatted)

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

    def test_checked_in_config_uses_research_report_stage2_template(self):
        config = Config("config.yaml")
        template = config.stage2_prompt_template

        self.assertIn("AI Daily Research Brief", template)
        self.assertIn("Executive Summary", template)
        self.assertIn("Key Signals", template)
        self.assertIn("Source Tier", template)
        self.assertIn("Verification", template)
        self.assertIn("Do not invent", template)

    def test_default_stage2_prompt_uses_research_report_structure(self):
        config = Config.__new__(Config)
        config.config_data = {}
        template = config.stage2_prompt_template

        self.assertIn("AI Daily Research Brief", template)
        self.assertIn("Executive Summary", template)
        self.assertIn("Key Signals", template)
        self.assertIn("Source Tier", template)
        self.assertIn("Source & Verification Notes", template)


if __name__ == "__main__":
    unittest.main()
