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
    "You are a medical research assistant supporting a specialist surgeon in Abu Dhabi. "
    "Your role is to research health topics thoroughly and provide structured, evidence-based findings "
    "to help create accurate patient education content. Always respond in JSON format."
)

# Blueprint 2H — User prompt structure (JSON request object)
# NOTE: Literal JSON braces are escaped as {{ and }} so Python's .format() doesn't
# treat them as format placeholders. Only {post_title} and {target_keyword} are real.
USER_PROMPT_TEMPLATE = """{{
  "research_topic": "{post_title}",
  "primary_keyword": "{target_keyword}",
  "research_questions": {{
    "medical_overview": "Provide a comprehensive medical overview of this topic. What does current clinical evidence say? Include key statistics, timeframes, and patient outcomes from medical literature.",
    "patient_questions": "What are the most common questions and misconceptions patients have about this topic? What do patients frequently misunderstand that a specialist surgeon should clarify?",
    "clinical_evidence": "List the most authoritative medical sources (peer-reviewed journals, clinical guidelines, medical societies) covering this topic. Include URLs where available.",
    "uae_context": "What specific considerations apply to patients in the UAE and Abu Dhabi? Include relevant cultural, dietary, religious (Ramadan if applicable), and regional health factors.",
    "specialist_insights": "What specialist-level clinical details are typically missing from general patient education materials on this topic? What would a laparoscopic surgeon or gastroenterologist emphasise that general sources overlook?",
    "citable_facts": "List 5-8 specific, verifiable medical facts and statistics about this topic that are well-supported by clinical evidence. For each, note the type of source that supports it."
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
