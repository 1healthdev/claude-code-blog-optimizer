"""
DataForSEO SERP API client — People Also Ask data.

Uses HTTP Basic Auth with click_depth=0 (4 top-level PAA questions)
to stay within server-side timeout limits.
Location: United Arab Emirates for localized results.
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

    def get_paa(self, keyword: str, depth: int = 0) -> str:
        """
        Fetch People Also Ask data for a keyword.
        depth=0 returns ~4 questions (safe, fast).
        depth=1 returns ~20 questions (slower).
        Returns a formatted string summary for inclusion in the Claude prompt.
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
                return f"PAA data unavailable: {error}"

            items = tasks[0].get("result", [{}])[0].get("items", [])

            # The organic endpoint returns PAA as one or more "people_also_ask" elements.
            # Each element may itself contain nested "items" with the individual questions.
            # We collect questions from both the top-level items and their nested children.
            questions = []
            for item in items:
                if item.get("type") != "people_also_ask":
                    continue
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

            if not questions:
                logger.warning(f"No PAA questions found for '{keyword}'")
                return "No People Also Ask data found for this keyword."

            lines = [f"People Also Ask — '{keyword}':"]
            for q in questions:
                lines.append(f"  Q: {q['question']}")
                if q["answer"]:
                    lines.append(f"     A: {q['answer'][:300]}")

            result = "\n".join(lines)
            logger.info(f"DataForSEO PAA: {len(questions)} questions for '{keyword}'")
            return result

        except requests.HTTPError as e:
            logger.warning(f"DataForSEO HTTP error for '{keyword}': {e}")
            return f"PAA data unavailable (HTTP error): {e}"
        except Exception as e:
            logger.warning(f"DataForSEO unexpected error for '{keyword}': {e}")
            return f"PAA data unavailable: {e}"
