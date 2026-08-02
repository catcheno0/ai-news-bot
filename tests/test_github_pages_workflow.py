from pathlib import Path
import unittest


class GitHubPagesWorkflowTests(unittest.TestCase):
    def test_daily_news_workflow_deploys_public_directory_to_pages(self):
        workflow = Path(".github/workflows/daily-news.yml").read_text(encoding="utf-8")

        self.assertIn("contents: read", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("actions/configure-pages@v5", workflow)
        self.assertIn("actions/upload-pages-artifact@v4", workflow)
        self.assertIn("actions/deploy-pages@v4", workflow)
        self.assertIn("PAGES_ENABLED: \"true\"", workflow)
        self.assertIn("PAGES_SITE_URL: https://news.my-ai-news.top", workflow)
        self.assertIn("path: public", workflow)
        self.assertIn("NOTIFICATION_METHODS: wechat_official", workflow)
        self.assertIn("WECHAT_OFFICIAL_APP_ID: ${{ secrets.WECHAT_OFFICIAL_APP_ID }}", workflow)
        self.assertIn("WECHAT_OFFICIAL_APP_SECRET: ${{ secrets.WECHAT_OFFICIAL_APP_SECRET }}", workflow)
        self.assertIn("WECHAT_OFFICIAL_OPENID: ${{ secrets.WECHAT_OFFICIAL_OPENID }}", workflow)
        self.assertIn("WECHAT_OFFICIAL_TEMPLATE_ID: ${{ secrets.WECHAT_OFFICIAL_TEMPLATE_ID }}", workflow)
        self.assertNotIn("PUSHPLUS_TOKEN", workflow)


if __name__ == "__main__":
    unittest.main()
