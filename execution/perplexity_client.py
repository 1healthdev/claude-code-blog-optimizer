"""
Perplexity API client — competitive research via sonar-pro model.

Configuration matches Make.com Blueprint v2.0 Section 2H exactly:
  - System role: Healthcare SEO Research Assistant, JSON output
  - User prompt: structured JSON request with post_title + target_keyword
  - return_citations: true
  - max_tokens: 4000
"""

import json
import logging

import requests

from config import Config

logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Blueprint 2H — System role
SYSTEM_ROLE = (
    "You are an expert Healthcare SEO Research Assistant. "
    "Conduct thorough research for medical content topics with attention to E-E-A-T signals. "
    "Provide output in JSON format."
)

# Blueprint 2H — User prompt structure (JSON request object)
# NOTE: Literal JSON braces are escaped as {{ and }} so Python's .format() doesn't
# treat them as format placeholders. Only {post_title} and {target_keyword} are real.
USER_PROMPT_TEMPLATE = """{{
  "topic": "{post_title}",
  "target_keyword": "{target_keyword}",
  "research_requirements": {{
    "competitor_synopses": "Analyze the top 5 ranking pages for this keyword. For each: title, key topics covered, estimated word count, content strengths, content weaknesses, and E-E-A-T signals used.",
    "evidence_sources": "List authoritative sources (medical journals, clinical guidelines, professional medical societies) cited by top-ranking content. Include URLs where available.",
    "content_gaps": "Identify specific subtopics, questions, or angles that top-ranking content does NOT cover well. Prioritize UAE/Abu Dhabi patient context and specialist-level clinical detail.",
    "ai_citation_assessment": "What specific factual claims, statistics, or clinical guidance about this topic would AI systems (Google AI Overviews, ChatGPT, Perplexity) most likely extract and cite? What structural or content factors make a passage citation-worthy?",
    "claims_needing_sources": "List 5-8 specific factual claims about this topic that require authoritative citations to be credible. Include recommended source types for each claim."
  }}
}}"""


class PerplexityClient:
    def __init__(self, cfg: Config):
        self.api_key = cfg.perplexity_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_competitive_analysis(self, post_title: str, target_keyword: str) -> str:
        """
        Run the Healthcare SEO Research prompt for a post.
        Uses both post_title and target_keyword as per Blueprint 2H.
        Returns a competitive intelligence string (JSON or fallback text).
        """
        user_content = USER_PROMPT_TEMPLATE.format(
            post_title=post_title,
            target_keyword=target_keyword,
        )

        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_ROLE,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "max_tokens": 4000,
            "temperature": 0.2,
            "return_citations": True,
        }

        try:
            resp = requests.post(
                PERPLEXITY_API_URL,
                headers=self.headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            content = data["choices"][0]["message"]["content"]

            # Attach citations block if returned
            citations = data.get("citations", [])
            if citations:
                citations_block = "\n\n### CITATIONS\n" + "\n".join(
                    f"[{i+1}] {url}" for i, url in enumerate(citations)
                )
                content = content + citations_block

            logger.info(
                f"Perplexity analysis: {len(content):,} chars for '{target_keyword}' "
                f"({len(citations)} citations)"
            )
            return content

        except requests.HTTPError as e:
            logger.warning(f"Perplexity HTTP error for '{target_keyword}': {e}")
            return f"Competitive analysis unavailable (HTTP error): {e}"
        except Exception as e:
            logger.warning(f"Perplexity unexpected error for '{target_keyword}': {e}")
            return f"Competitive analysis unavailable: {e}"
