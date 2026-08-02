"""WeChat Official Account test account notification module."""
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

import requests

from ..logger import setup_logger


logger = setup_logger(__name__)


class WeChatOfficialNotifier:
    """Send template messages through a WeChat Official Account test account."""

    TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
    SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        openid: Optional[str] = None,
        template_id: Optional[str] = None,
        timeout: int = 30,
    ):
        self.app_id = app_id or os.getenv("WECHAT_OFFICIAL_APP_ID")
        self.app_secret = app_secret or os.getenv("WECHAT_OFFICIAL_APP_SECRET")
        self.openid = openid or os.getenv("WECHAT_OFFICIAL_OPENID")
        self.template_id = template_id or os.getenv("WECHAT_OFFICIAL_TEMPLATE_ID")
        self.timeout = timeout
        self._access_token: Optional[str] = None
        self._access_token_expires_at = 0.0

        if not self._is_configured():
            logger.warning("WeChat Official Account settings are incomplete")
        else:
            logger.info("WeChatOfficialNotifier initialized")

    def send(
        self,
        content: str,
        title: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> bool:
        if not self._is_configured():
            logger.error("WeChat Official Account settings are incomplete. Skipping send.")
            return False

        try:
            if title is None:
                today = datetime.now().strftime("%Y-%m-%d")
                lang_suffix = f" [{language.upper()}]" if language != "en" else ""
                title = f"AI News Digest - {today}{lang_suffix}"

            access_token = self._get_access_token()
            payload = {
                "touser": self.openid,
                "template_id": self.template_id,
                "url": self._resolve_page_url(additional_data),
                "data": self._build_template_data(title, content),
            }

            response = requests.post(
                self.SEND_URL.format(access_token=quote(access_token, safe="")),
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            if int(result.get("errcode", -1)) == 0:
                logger.info("WeChat Official Account notification sent successfully")
                return True

            logger.error(f"WeChat Official Account API error: {result}")
            return False

        except requests.exceptions.Timeout:
            logger.error(f"WeChat Official Account request timed out after {self.timeout}s")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WeChat Official Account notification: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error in WeChat Official Account notifier: {str(e)}", exc_info=True)
            return False

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expires_at - 60:
            return self._access_token

        params = urlencode(
            {
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            }
        )
        response = requests.get(f"{self.TOKEN_URL}?{params}", timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            raise RuntimeError(f"Failed to get WeChat access_token: {data}")

        self._access_token = str(access_token)
        self._access_token_expires_at = time.time() + int(data.get("expires_in", 7200))
        return self._access_token

    def _build_template_data(self, title: str, content: str) -> Dict[str, Dict[str, str]]:
        return {
            "first": {"value": "AI Daily generated"},
            "keyword1": {"value": title[:64]},
            "keyword2": {"value": datetime.now().strftime("%Y-%m-%d %H:%M")},
            "keyword3": {"value": self._summarize_content(content)},
            "remark": {"value": "Open the message to read the full digest."},
        }

    def _resolve_page_url(self, additional_data: Optional[Dict[str, Any]]) -> str:
        if additional_data and additional_data.get("page_url"):
            return str(additional_data["page_url"]).strip()
        return os.getenv("WECHAT_OFFICIAL_DETAIL_URL", "").strip()

    def _summarize_content(self, content: str) -> str:
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
        text = re.sub(r"[#>*_`~\-]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return (text or "AI daily digest is ready.")[:120]

    def _is_configured(self) -> bool:
        return all([self.app_id, self.app_secret, self.openid, self.template_id])
