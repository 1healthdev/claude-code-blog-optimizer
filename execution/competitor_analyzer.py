"""
Competitor page analyser — Step 3D of the data-gathering phase.

Takes the top organic SERP URLs already returned by DataForSEO,
scrapes each one with requests + BeautifulSoup, then calls Claude
to produce a structured competitor analysis brief.

Output is appended to the Perplexity research data in Column AD so
blog_analyst and content_generator receive it automatically — no
schema changes required.

Scraping approach:
  - Uses plain requests + BeautifulSoup (free, no API key needed).
  - Works for most medical content sites (NIH, PubMed, Mayo, NHS, BMJ).
  - Pages that block scraping are silently marked "inaccessible" and skipped.
  - ScrapeOwl upgrade: set SCRAPEOWL_API_KEY in .env to enable JS-rendered
    page support. Falls back to plain requests if key is absent.
"""

import json
import logging

import anthropic
import requests
from bs4 import BeautifulSoup

from config import Config

logger = logging.getLogger(__name__)

# --- HTTP scraping config ---

_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_SCRAPE_TIMEOUT = 10   # seconds per page
_MAX_EXCERPT_CHARS = 2000  # chars of body text to send to Claude per page
_MAX_HEADINGS = 15         # H2/H3 headings per page


# --- Claude prompt ---

_SYSTEM_PROMPT = (
    "You are a medical content strategist. You will be given scraped content from "
    "competitor web pages currently ranking for a medical keyword. "
    "Your job is to analyse them and identify strategic content opportunities for a "
    "specialist surgeon's patient education article. "
    "Always respond with valid JSON only — no markdown, no text outside the JSON object."
)

_USER_TEMPLATE = """\
Analyse these competitor pages currently ranking for the keyword: "{keyword}"

Post title we are creating: "{post_title}"

COMPETITOR PAGE DATA:
{pages_block}

Return ONLY a JSON object in this exact format (no markdown fences):
{{
  "competitors": [
    {{
      "url": "<url>",
      "title": "<page title>",
      "estimated_word_count": <int>,
      "main_topics": ["<topic1>", "<topic2>"],
      "faq_count": <int or 0 if unknown>,
      "key_strengths": ["<strength1>", "<strength2>"],
      "content_gaps": ["<gap1>", "<gap2>"],
      "evidence_quality": "high|medium|low"
    }}
  ],
  "strategic_opportunities": [
    "<opportunity1>",
    "<opportunity2>",
    "<opportunity3>"
  ]
}}

Focus especially on: UAE/Abu Dhabi context missing, laparoscopic or specialist \
surgical perspective absent, Ramadan or cultural health factors ignored, \
weak citation quality, missing patient safety information."""


# --- ScrapeOwl helper (optional) ---

def _scrapeowl_fetch(url: str, api_key: str) -> str:
    """Fetch a URL via ScrapeOwl API. Returns HTML or raises on error."""
    resp = requests.get(
        "https://api.scrapeowl.com/v1/scrape",
        params={"api_key": api_key, "url": url, "render_js": "false"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("html", "")


# --- Main class ---

class CompetitorAnalyzer:
    """Scrape top competitor pages and produce a structured competitor analysis."""

    def __init__(self, cfg: Config):
        # 2-minute read timeout — competitor analysis outputs ~1.5K tokens.
        self.client = anthropic.Anthropic(
            api_key=cfg.anthropic_api_key,
            timeout=anthropic.Timeout(connect=15.0, read=120.0, write=15.0, pool=15.0),
        )
        # Optional ScrapeOwl support — set SCRAPEOWL_API_KEY in .env to enable.
        self._scrapeowl_key: str | None = getattr(cfg, "scrapeowl_api_key", None) or None

    def _fetch_html(self, url: str) -> str:
        """Fetch raw HTML from a URL using ScrapeOwl (if configured) or plain requests."""
        if self._scrapeowl_key:
            try:
                return _scrapeowl_fetch(url, self._scrapeowl_key)
            except Exception as e:
                logger.debug(f"ScrapeOwl fetch failed for {url}, falling back to requests: {e}")

        resp = requests.get(url, headers=_SCRAPE_HEADERS, timeout=_SCRAPE_TIMEOUT)
        resp.raise_for_status()
        return resp.text

    def _scrape(self, url: str) -> dict:
        """Scrape a single URL. Returns a content dict or marks page as inaccessible."""
        try:
            html = self._fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")

            # Strip boilerplate tags before extracting text
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
                tag.decompose()

            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else url

            headings = [
                h.get_text(strip=True)
                for h in soup.find_all(["h2", "h3"])
            ][:_MAX_HEADINGS]

            body_text = soup.get_text(separator=" ", strip=True)
            word_count = len(body_text.split())

            return {
                "url": url,
                "title": title,
                "estimated_word_count": word_count,
                "headings": headings,
                "excerpt": body_text[:_MAX_EXCERPT_CHARS],
                "accessible": True,
            }

        except Exception as e:
            logger.debug(f"Competitor scrape failed for {url}: {e}")
            return {
                "url": url,
                "title": "inaccessible",
                "estimated_word_count": 0,
                "headings": [],
                "excerpt": "",
                "accessible": False,
            }

    def analyze(self, urls: list[str], keyword: str, post_title: str) -> str:
        """
        Scrape up to 5 competitor URLs and call Claude for structured analysis.
        Returns a formatted string to append to perplexity_data in Column AD.
        Falls back gracefully if all pages are inaccessible or Claude fails.
        """
        if not urls:
            logger.info("Competitor analysis: no URLs provided, skipping.")
            return "Competitor analysis: no organic SERP URLs available for this keyword."

        target_urls = urls[:5]
        scraped = [self._scrape(u) for u in target_urls]
        accessible = [p for p in scraped if p["accessible"]]
        inaccessible = [p for p in scraped if not p["accessible"]]

        logger.info(
            f"Competitor scraping: {len(accessible)}/{len(target_urls)} URLs accessible "
            f"for '{keyword}'"
        )

        if not accessible:
            logger.warning(
                f"Competitor analysis: all {len(target_urls)} URLs inaccessible, "
                "skipping Claude call."
            )
            return (
                "Competitor analysis: all competitor pages blocked scraping. "
                f"URLs attempted: {', '.join(target_urls)}"
            )

        # Build pages block for the Claude prompt
        parts = []
        for p in accessible:
            parts.append(
                f"URL: {p['url']}\n"
                f"Title: {p['title']}\n"
                f"Estimated word count: {p['estimated_word_count']}\n"
                f"H2/H3 headings: {' | '.join(p['headings']) if p['headings'] else 'none found'}\n"
                f"Content excerpt:\n{p['excerpt']}"
            )
        for p in inaccessible:
            parts.append(f"URL: {p['url']}\nStatus: INACCESSIBLE — blocked scraping")

        pages_block = "\n\n---\n\n".join(parts)

        user_content = _USER_TEMPLATE.format(
            keyword=keyword,
            post_title=post_title,
            pages_block=pages_block,
        )

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            result_text = message.content[0].text.strip()

            # Strip any accidental markdown fences
            if result_text.startswith("```"):
                lines = result_text.splitlines()
                result_text = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                ).strip()

            # Validate parseable JSON (don't reject — just warn if malformed)
            try:
                json.loads(result_text)
            except json.JSONDecodeError:
                logger.warning(
                    "Competitor analysis: Claude returned non-JSON; storing raw text."
                )

            logger.info(
                f"Competitor analysis: {len(result_text):,} chars, "
                f"{len(accessible)}/{len(target_urls)} URLs accessible for '{keyword}'"
            )
            return result_text

        except Exception as e:
            logger.warning(f"Competitor analysis Claude call failed for '{keyword}': {e}")
            return f"Competitor analysis unavailable: {e}"
