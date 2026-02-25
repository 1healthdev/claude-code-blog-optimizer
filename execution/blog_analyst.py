"""
Blog Analyst — Layer 2 intelligence step.
Loads all 5 knowledge files, combines them with the post's research data,
and calls Claude to produce a compact analysis brief (~1,200 words).
The brief is then passed to content_generator.py for final content creation.
"""

import logging
from pathlib import Path

import anthropic
import pypdf

from config import Config, KNOWLEDGE_DIR
from data_gatherer import ResearchData
from sheets_client import PostRow

logger = logging.getLogger(__name__)

ANALYST_SYSTEM_PROMPT = """You are Blog_Analyst, an expert medical SEO content strategist for Dr. Rajarshi Mitra's surgical practice in Abu Dhabi.

Your job is to produce a compact, actionable Analysis Brief (~1,200 words) that will be used by a content generation system to optimize a blog post.

You have been loaded with 5 knowledge files that define the complete optimization standards. Apply them intelligently based on the post's content type and platform category.

Produce your Analysis Brief in this exact structure:

## ANALYSIS BRIEF

### Post Intelligence
- Post title, URL, target keyword
- Platform category (BING_DOMINANT / GOOGLE_DOMINANT / BALANCED) and what it means for this post
- Content tier (0=pillar, 1=primary, 2=secondary, 3=supporting) and target word count

### Optimization Strategy
- 3-5 specific, actionable optimization priorities for THIS post
- Key differentiators vs. competitor content (from Perplexity data)
- Whether Ramadan overlay applies (yes/no) and why

### Keyword & Structure Plan
- Recommended H1 (include exact target keyword)
- 8-13 recommended H2 section titles (question-format where possible, using PAA data)
- 3-5 key semantic terms to weave throughout content

### FAQ Strategy
- Number of FAQ questions required (15+ for BING_DOMINANT, 10+ standard)
- Top 8-10 specific FAQ questions to include (sourced from PAA and Perplexity data)
- Which questions are highest-priority for AI citation (Google AI Overviews, ChatGPT)

### Evidence & Citations Plan
- Minimum inline citations required for this tier
- 5-8 specific types of evidence to include (statistics, guidelines, clinical studies)
- Recommended authoritative sources to cite

### Special Elements Checklist
- [ ] Ramadan elements required? (moon sighting disclaimer, IDF-DAR guidelines, etc.)
- [ ] Bing-specific elements required? (exact keyword in H1 + first paragraph)
- [ ] Myth-busting topics (list 3 specific myths to debunk for this post)
- [ ] Lead magnets applicable? (list relevant ones from Ramadan addendum if applicable)

Keep the brief focused and actionable. Do not generate any HTML or final content — that comes next."""


def _extract_pdf_text(path: Path) -> str:
    """Extract plain text from a PDF file using pypdf."""
    reader = pypdf.PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _load_knowledge_files(knowledge_dir: Path) -> str:
    """
    Load and concatenate all knowledge PDFs from the knowledge/ directory.
    Globs all *.pdf files — picks up any file added in future, not just the original 5.
    """
    pdf_files = sorted(knowledge_dir.glob("*.pdf"))

    if not pdf_files:
        logger.error(
            f"No PDF files found in {knowledge_dir}. "
            "Please place the 5 knowledge .md.pdf files there."
        )
        return "WARNING: No knowledge files loaded. Place .md.pdf files in the knowledge/ directory."

    sections = []
    for path in pdf_files:
        try:
            text = _extract_pdf_text(path)
            sections.append(f"{'='*60}\n# KNOWLEDGE FILE: {path.name}\n{'='*60}\n\n{text}")
            logger.info(f"Loaded knowledge file: {path.name} ({len(text):,} chars)")
        except Exception as e:
            logger.warning(f"Failed to read {path.name}: {e}")

    logger.info(f"Loaded {len(sections)} of {len(pdf_files)} knowledge files")
    return "\n\n".join(sections)


class BlogAnalyst:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        self._knowledge_cache: str | None = None

    def _get_knowledge(self) -> str:
        if self._knowledge_cache is None:
            self._knowledge_cache = _load_knowledge_files(self.cfg.knowledge_dir)
        return self._knowledge_cache

    def generate_brief(
        self,
        row: PostRow,
        research: ResearchData,
        current_content: str | None,
    ) -> str:
        """
        Generate the analysis brief for a post.
        Returns the brief text to be passed to content_generator.
        """
        knowledge = self._get_knowledge()

        user_message = f"""Please produce an Analysis Brief for the following post.

## Post Details
- **Title**: {row.post_title}
- **URL**: {row.post_url}
- **Post ID**: {row.post_id}
- **Target Keyword**: {row.target_keyword}
- **Platform Category**: {row.platform_category}

## Current Post Content (if available)
{current_content or "Not available — this may be a new post."}

## Research Data

### People Also Ask (DataForSEO)
{research.paa_data}

### Keyword Intelligence (Ahrefs)
{research.ahrefs_data}

### Competitive Analysis (Perplexity)
{research.perplexity_data}

---

Please now produce the Analysis Brief following the structure in your instructions."""

        system_with_knowledge = f"{ANALYST_SYSTEM_PROMPT}\n\n{knowledge}"

        logger.info(f"Generating analysis brief for: {row.post_title}")
        logger.debug(f"System prompt: {len(system_with_knowledge):,} chars")

        message = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            system=system_with_knowledge,
            messages=[{"role": "user", "content": user_message}],
        )

        brief = message.content[0].text
        logger.info(f"Analysis brief generated: {len(brief):,} chars")
        return brief
