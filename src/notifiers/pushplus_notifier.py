"""
PushPlus notification module
"""
import os
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from ..logger import setup_logger


logger = setup_logger(__name__)


class PushPlusNotifier:
    """Send notifications via PushPlus (微信推送)"""

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: int = 30
    ):
        self.token = token or os.getenv("PUSHPLUS_TOKEN")
        self.timeout = timeout

        if not self.token:
            logger.warning("PUSHPLUS_TOKEN not configured")
        else:
            logger.info(f"PushPlusNotifier initialized (token: {self.token[:8]}***)")

    def send(
        self,
        content: str,
        title: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        language: str = "en"
    ) -> bool:
        if not self.token:
            logger.error("PUSHPLUS_TOKEN not configured. Skipping pushplus send.")
            return False

        try:
            if title is None:
                today = datetime.now().strftime("%Y-%m-%d")
                lang_suffix = f" [{language.upper()}]" if language != "en" else ""
                title = f"AI News Digest - {today}{lang_suffix}"

            payload = {
                "token": self.token,
                "title": title,
                "content": content,
                "template": "markdown"
            }

            response = requests.post(
                "https://www.pushplus.plus/send",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            result = response.json()

            if result.get("code") == 200:
                logger.info("PushPlus notification sent successfully")
                return True
            else:
                logger.error(f"PushPlus API error: code={result.get('code')}, msg={result.get('msg')}")
                return False

        except requests.exceptions.Timeout:
            logger.error(f"PushPlus request timed out after {self.timeout}s")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send PushPlus notification: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error in PushPlus: {str(e)}", exc_info=True)
            return False
