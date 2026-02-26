"""
Content Generator — single Claude API call to produce the complete 8-part deliverable.

Uses the user's complete optimization prompt stored in:
  .agent/skills/blog-optimizer/references/content-generation-prompt.md

With claude-sonnet-4-5 supporting 64K max output tokens, the entire post
(HTML body + FAQ + schema + meta + all 8 parts) is generated in one call.
No module splitting needed — that was a Make.com constraint only.

User message format mirrors Make.com Blueprint v2.0 Section 3C input mapping exactly,
including all 30 Sheet columns and the "may be empty — proceed regardless" directive
for GSC/Bing metrics.
"""

import logging
from pathlib import Path

import anthropic

from config import Config
from data_gatherer import ResearchData
from sheets_client import PostRow

logger = logging.getLogger(__name__)

PROMPT_FILE = (
    Path(__file__).parent.parent
    / ".agent/skills/blog-optimizer/references/content-generation-prompt.md"
)

FALLBACK_SYSTEM_PROMPT = """You are an expert medical SEO content writer for Dr. Rajarshi Mitra's surgical practice in Abu Dhabi.

Generate the complete optimized blog post deliverable based on the Analysis Brief and research data provided.

IMPORTANT: The content-generation-prompt.md file has not been added yet.
Please add your complete optimization prompt to:
  .agent/skills/blog-optimizer/references/content-generation-prompt.md

For now, generate a placeholder response indicating the prompt file is missing."""


def _load_generation_prompt() -> str:
    if PROMPT_FILE.exists():
        content = PROMPT_FILE.read_text(encoding="utf-8")
        logger.info(f"Loaded content generation prompt: {len(content):,} chars")
        return content
    else:
        logger.warning(
            f"Content generation prompt not found at:\n  {PROMPT_FILE}\n"
            "Using fallback prompt. Please add your complete optimization prompt to that file."
        )
        return FALLBACK_SYSTEM_PROMPT


class ContentGenerator:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        # 10-minute read timeout — content_generator requests up to 64K output tokens.
        # Without a timeout the call can hang indefinitely if the API is slow.
        # anthropic.APITimeoutError is raised on timeout; pipeline.py catches it and
        # marks the row Error so the next post can proceed.
        self.client = anthropic.Anthropic(
            api_key=cfg.anthropic_api_key,
            timeout=anthropic.Timeout(connect=15.0, read=600.0, write=15.0, pool=15.0),
        )
        self._prompt_cache: str | None = None

    def _get_prompt(self) -> str:
        if self._prompt_cache is None:
            self._prompt_cache = _load_generation_prompt()
        return self._prompt_cache

    def generate(
        self,
        row: PostRow,
        research: ResearchData,
        brief: str,
        current_content: str | None,
    ) -> str:
        """
        Generate the complete optimized post in a single Claude API call.
        Returns the full deliverable as a string (HTML + all 8 parts).

        User message mirrors Blueprint v2.0 Section 3C input mapping — all Sheet
        columns are passed explicitly so the model has the full strategic context.
        GSC/Bing metrics are included with a clear "may be empty — proceed regardless"
        directive so missing data never blocks optimization.
        """
        system_prompt = self._get_prompt()

        # Section 3C input format — matches Make.com blueprint exactly
        user_message = f"""OPTIMIZE THIS POST:
Title: {row.post_title}
URL: {row.post_url}
Post ID: {row.post_id}
Target Keyword: {row.target_keyword}
Secondary Keywords: {row.secondary_keywords or "Not specified"}
Tier: {row.tier or "Not specified"}
Platform Category: {row.platform_category}
Section: {row.section or "Not specified"}
Post Type: {row.post_type or "Not specified"}
Description: {row.description or "Not specified"}

GOOGLE SEARCH CONSOLE METRICS (may be empty — proceed regardless, do not treat as an error):
Impressions: {row.gsc_impressions or "—"} | Clicks: {row.gsc_clicks or "—"} | CTR: {row.gsc_ctr or "—"} | Position: {row.gsc_position or "—"}

BING WEBMASTER TOOLS METRICS (may be empty — proceed regardless, do not treat as an error):
Impressions: {row.bing_impressions or "—"} | Clicks: {row.bing_clicks or "—"} | CTR: {row.bing_ctr or "—"} | Position: {row.bing_position or "—"}

Notes: {row.notes or "None"}

== ANALYSIS BRIEF (from Blog_Analyst) ==
{brief}

== PAA DATA (from DataForSEO) ==
{research.paa_data}

== AHREFS KEYWORD DATA ==
{research.ahrefs_data}

== PERPLEXITY COMPETITIVE INTELLIGENCE ==
{research.perplexity_data}

== CURRENT POST CONTENT ==
{current_content or "Not available — treat as a new post and generate from scratch."}

---
Please generate the complete optimized post deliverable now (all 8 parts)."""

        logger.info(f"Generating content for: {row.post_title}")
        logger.debug(f"User message: {len(user_message):,} chars")

        # Large max_tokens requires streaming mode in the Anthropic SDK
        # (non-streaming times out for requests that may take >10 minutes)
        with self.client.messages.stream(
            model="claude-sonnet-4-5-20250929",
            max_tokens=64000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            output = stream.get_final_text()
            message = stream.get_final_message()

        logger.info(
            f"Content generated: {len(output):,} chars "
            f"(input: {message.usage.input_tokens:,} tokens, "
            f"output: {message.usage.output_tokens:,} tokens)"
        )

        # Warn if output was cut off near the token limit
        if message.stop_reason == "max_tokens":
            logger.warning(
                f"Output hit max_tokens limit ({message.usage.output_tokens:,}). "
                "Content may be truncated. Increase max_tokens in content_generator.py "
                "(current: 32,000; max supported: 64,000)."
            )

        return output
