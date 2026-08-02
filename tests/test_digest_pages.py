from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from src.news.pages import DigestPagePublisher


class DigestPagePublisherTests(unittest.TestCase):
    def test_publish_writes_latest_and_dated_html_with_page_urls(self):
        generated_at = datetime(2026, 8, 2, 8, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmp_dir:
            publisher = DigestPagePublisher(
                output_dir=tmp_dir,
                site_url="https://news.my-ai-news.top",
            )

            published = publisher.publish(
                "# AI Daily\n\n- [OpenAI](https://openai.com/news)",
                language="zh",
                generated_at=generated_at,
                primary=True,
            )

            latest_path = Path(tmp_dir) / "latest.html"
            dated_path = Path(tmp_dir) / "2026-08-02.html"

            self.assertTrue(latest_path.exists())
            self.assertTrue(dated_path.exists())
            self.assertEqual(published.latest_url, "https://news.my-ai-news.top/latest.html")
            self.assertEqual(published.dated_url, "https://news.my-ai-news.top/2026-08-02.html")

            latest_html = latest_path.read_text(encoding="utf-8")
            self.assertIn("<h1>AI Daily</h1>", latest_html)
            self.assertIn('<a href="https://openai.com/news">OpenAI</a>', latest_html)

    def test_publish_escapes_raw_html_before_rendering_markdown(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            publisher = DigestPagePublisher(output_dir=tmp_dir, site_url="")

            publisher.publish(
                "# Title\n\n<script>alert(1)</script>\n\n[Source](https://example.com?a=1&b=2)",
                language="en",
                generated_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
                primary=True,
            )

            html = (Path(tmp_dir) / "latest.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertIn('href="https://example.com?a=1&amp;b=2"', html)

