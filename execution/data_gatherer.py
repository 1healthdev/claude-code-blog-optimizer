"""
Data gathering orchestrator.
Runs DataForSEO PAA + Perplexity competitive research + competitor page analysis
for a post.
Ahrefs data is pre-populated in Column S by Claude Code MCP (Layer 2 orchestrator)
before this pipeline runs — this module simply reads it from the PostRow.

Step 3D (competitor_analyzer) scrapes the top organic URLs already returned by
DataForSEO, analyses them with Claude, and appends the result to the Perplexity
data before saving to Column AD. No schema changes required.
"""

import logging
from dataclasses import dataclass

from competitor_analyzer import CompetitorAnalyzer
from config import Config
from dataforseo_client import DataForSEOClient
from perplexity_client import PerplexityClient
from sheets_client import PostRow, SheetsClient

logger = logging.getLogger(__name__)


@dataclass
class ResearchData:
    paa_data: str
    ahrefs_data: str       # Pre-populated by Claude Code MCP before pipeline runs
    perplexity_data: str   # Perplexity medical research + competitor analysis (combined)


class DataGatherer:
    def __init__(self, cfg: Config, sheets: SheetsClient):
        self.cfg = cfg
        self.sheets = sheets
        self.dataforseo = DataForSEOClient(cfg)
        self.perplexity = PerplexityClient(cfg)
        self.competitor_analyzer = CompetitorAnalyzer(cfg)

    def gather(self, row: PostRow) -> ResearchData:
        """
        Gather all research data for a post.
        Steps:
          3A: DataForSEO → PAA questions + top organic URLs → Col R
          3B: Ahrefs → keyword metrics (pre-populated, read from Col S)
          3C: Perplexity → medical research → Col AD
          3D: CompetitorAnalyzer → scrape + analyse top 3-5 pages → appended to Col AD
        """
        keyword = row.target_keyword
        logger.info(f"Gathering research data for: '{keyword}'")

        # --- 3A: DataForSEO PAA + organic URLs ---
        logger.info(f"  → DataForSEO PAA + organic SERP URLs...")
        paa_data, organic_urls = self.dataforseo.get_paa(keyword)
        self.sheets.save_paa_data(row, paa_data)

        # --- 3B: Ahrefs (pre-populated by Claude Code MCP) ---
        ahrefs_data = row.ahrefs_data
        if not ahrefs_data:
            logger.warning(
                f"  ⚠ Ahrefs data missing for '{keyword}' (Column S empty). "
                "Run the Ahrefs MCP pre-step in Claude Code before running the pipeline. "
                "Continuing without Ahrefs data."
            )
            ahrefs_data = "Ahrefs data not available for this post."
        else:
            logger.info(f"  → Ahrefs data: {len(ahrefs_data):,} chars (pre-populated)")

        # --- 3C: Perplexity medical research ---
        logger.info(f"  → Perplexity medical research...")
        perplexity_data = self.perplexity.get_competitive_analysis(
            post_title=row.post_title,
            target_keyword=keyword,
        )

        # --- 3D: Competitor page analysis ---
        logger.info(
            f"  → Competitor analysis ({len(organic_urls)} organic URLs from DataForSEO)..."
        )
        competitor_data = self.competitor_analyzer.analyze(
            urls=organic_urls,
            keyword=keyword,
            post_title=row.post_title,
        )

        # Combine Perplexity research + competitor analysis into one Column AD value.
        # blog_analyst and content_generator receive this as a single string — no
        # schema changes needed.
        combined_research = (
            perplexity_data
            + "\n\n"
            + "=" * 60
            + "\n### COMPETITOR PAGE ANALYSIS\n"
            + "=" * 60
            + "\n"
            + competitor_data
        )
        self.sheets.save_perplexity_data(row, combined_research)

        return ResearchData(
            paa_data=paa_data,
            ahrefs_data=ahrefs_data,
            perplexity_data=combined_research,
        )
