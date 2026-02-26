"""
DataForSEO SERP API client — People Also Ask data + top organic URLs.

Uses HTTP Basic Auth with click_depth=0 (4 top-level PAA questions)
to stay within server-side timeout limits.
Location: United Arab Emirates for localized results.

get_paa() returns a tuple: (paa_text: str, organic_urls: list[str])
The organic_urls are the top-ranking pages for the keyword — fed to
competitor_analyzer.py for scraping and analysis.
"""

import base64
import json
import logging
import time
from typing import Optional

import requests

from config import Config

logger = logging.getLogger(__name__)

# people_also_ask/live/advanced is only available on higher-tier plans.
# organic/live/advanced returns the full SERP including PAA items — available on all plans.
PAA_ENDPOINT = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"


def _extract_answer(item: dict) -> str:
    """Pull the best available answer text from a PAA item."""
    # Try expanded_element first (richer answer)
    expanded = item.get("expanded_element", [])
    if isinstance(expanded, list) and expanded:
        text = expanded[0].get("featured_title", "") or expanded[0].get("description", "")
        if text:
            return text.strip()
    # Fallback to description directly on item
    return item.get("description", "").strip()


class DataForSEOClient:
    def __init__(self, cfg: Config):
        token = base64.b64encode(
            f"{cfg.dataforseo_login}:{cfg.dataforseo_password}".encode()
        ).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    def get_paa(self, keyword: str, depth: int = 0) -> tuple[str, list[str]]:
        """
        Fetch People Also Ask data + top organic URLs for a keyword.
        depth=0 returns ~4 questions (safe, fast).
        depth=1 returns ~20 questions (slower).
        Returns a tuple:
          - paa_text: formatted string of PAA questions for Claude prompt
          - organic_urls: list of top organic SERP URLs for competitor analysis
        On error returns (error_string, []).
        """
        payload = [
            {
                "keyword": keyword,
                "location_name": "United Arab Emirates",
                "language_name": "English",
                "se_results_count": 100,   # More SERP items → more PAA elements captured
            }
        ]

        try:
            resp = requests.post(
                PAA_ENDPOINT,
                headers=self.headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            tasks = data.get("tasks", [])
            if not tasks or tasks[0].get("status_code") != 20000:
                error = tasks[0].get("status_message", "Unknown error") if tasks else "No tasks returned"
                logger.warning(f"DataForSEO PAA error for '{keyword}': {error}")
                return f"PAA data unavailable: {error}", []

            items = tasks[0].get("result", [{}])[0].get("items", [])

            # The organic endpoint returns PAA as one or more "people_also_ask" elements.
            # Each element may itself contain nested "items" with the individual questions.
            # We collect questions from both the top-level items and their nested children.
            # We also collect organic result URLs for competitor analysis (Step 3D).
            questions = []
            organic_urls: list[str] = []
            seen_urls: set[str] = set()

            for item in items:
                item_type = item.get("type", "")

                if item_type == "people_also_ask":
                    # Top-level question (the collapsed PAA box title)
                    if item.get("title"):
                        questions.append({
                            "question": item["title"],
                            "answer": _extract_answer(item),
                        })
                    # Nested expanded questions inside the PAA block
                    for sub in item.get("items", []):
                        if sub.get("title"):
                            questions.append({
                                "question": sub["title"],
                                "answer": _extract_answer(sub),
                            })

                elif item_type == "organic":
                    # Collect top organic URLs for competitor analysis
                    url = item.get("url", "").strip()
                    if url and url not in seen_urls and len(organic_urls) < 10:
                        organic_urls.append(url)
                        seen_urls.add(url)

            if not questions:
                logger.warning(f"No PAA questions found for '{keyword}'")
                paa_text = "No People Also Ask data found for this keyword."
            else:
                lines = [f"People Also Ask — '{keyword}':"]
                for q in questions:
                    lines.append(f"  Q: {q['question']}")
                    if q["answer"]:
                        lines.append(f"     A: {q['answer'][:300]}")
                paa_text = "\n".join(lines)

            logger.info(
                f"DataForSEO PAA: {len(questions)} questions + "
                f"{len(organic_urls)} organic URLs for '{keyword}'"
            )
            return paa_text, organic_urls

        except requests.HTTPError as e:
            logger.warning(f"DataForSEO HTTP error for '{keyword}': {e}")
            return f"PAA data unavailable (HTTP error): {e}", []
        except Exception as e:
            logger.warning(f"DataForSEO unexpected error for '{keyword}': {e}")
            return f"PAA data unavailable: {e}", []
