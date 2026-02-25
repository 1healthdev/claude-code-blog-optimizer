"""
WordPress REST API client.
Fetches the current HTML content of a post by its post ID.
Authentication: WordPress Application Password (username + app password).
"""

import base64
import logging
from typing import Optional

import requests

from config import Config

logger = logging.getLogger(__name__)


class WordPressClient:
    def __init__(self, cfg: Config):
        self.base_url = cfg.wp_site_url.rstrip("/")
        token = base64.b64encode(
            f"{cfg.wp_username}:{cfg.wp_api_key}".encode()
        ).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    def fetch_post_content(self, post_id: str) -> Optional[str]:
        """
        Fetch the raw HTML content of a WordPress post by its ID.
        Returns the rendered content string, or None on failure.
        """
        if not post_id:
            logger.warning("No post ID provided — skipping WordPress fetch")
            return None

        url = f"{self.base_url}/wp-json/wp/v2/posts/{post_id}"
        try:
            # Try unauthenticated first — published posts are publicly readable.
            # Some security plugins block Basic Auth on REST API but allow public reads.
            resp = requests.get(url, timeout=30)
            if resp.status_code == 403:
                logger.debug(f"Unauthenticated fetch blocked for post {post_id}, retrying with auth...")
                resp = requests.get(url, headers=self.headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", {}).get("rendered", "")
            logger.info(f"Fetched post {post_id} — {len(content):,} chars")
            return content
        except requests.HTTPError as e:
            logger.warning(f"WordPress fetch failed for post {post_id}: {e}")
            logger.warning(
                "If this is a 403, check: (1) WordPress REST API is not blocked by a "
                "security plugin (Wordfence, iThemes, etc.), (2) Application Password "
                "exists at WP Admin → Users → Profile → Application Passwords."
            )
            return None
        except Exception as e:
            logger.warning(f"Unexpected error fetching post {post_id}: {e}")
            return None
