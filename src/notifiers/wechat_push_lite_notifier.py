"""
Self-hosted WeChat Push Lite notification module
"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from ..logger import setup_logger


logger = setup_logger(__name__)


class WeChatPushLiteNotifier:
    """Send notifications via the local self-hosted WeChat push backend."""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 30,
    ):
        self.url = url or os.getenv("WECHAT_PUSH_LITE_URL", "http://127.0.0.1:8000/api/send")
        self.token = token or os.getenv("WECHAT_PUSH_LITE_TOKEN") or os.getenv("PUSH_API_TOKEN")
        self.timeout = timeout

        if not self.token:
            logger.warning("WECHAT_PUSH_LITE_TOKEN or PUSH_API_TOKEN not configured")
        else:
            logger.info(f"WeChatPushLiteNotifier initialized (URL: {self._mask_url(self.url)})")

    def send(
        self,
        content: str,
        title: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> bool:
        if not self.token:
            logger.error("WeChat Push Lite token not configured. Skipping send.")
            return False

        try:
            if title is None:
                today = datetime.now().strftime("%Y-%m-%d")
                lang_suffix = f" [{language.upper()}]" if language != "en" else ""
                title = f"AI News Digest - {today}{lang_suffix}"

            payload = {
                "title": title,
                "content": content,
                "template": "markdown",
            }

            if additional_data:
                payload.update(additional_data)

            response = requests.post(
                self.url,
                json=payload,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            result = response.json()

            if result.get("status") == "sent":
                logger.info("WeChat Push Lite notification sent successfully")
                return True

            logger.error(f"WeChat Push Lite API error: {result}")
            return False

        except requests.exceptions.Timeout:
            logger.error(f"WeChat Push Lite request timed out after {self.timeout}s")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WeChat Push Lite notification: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error in WeChat Push Lite: {str(e)}", exc_info=True)
            return False

    def _mask_url(self, url: str) -> str:
        if not url:
            return ""

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}/***"
        except Exception:
            return "***"
