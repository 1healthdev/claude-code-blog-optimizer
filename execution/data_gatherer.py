"""
Data gathering orchestrator.
Runs DataForSEO PAA + Perplexity competitive research for a post.
Ahrefs data is pre-populated in Column S by Claude Code MCP (Layer 2 orchestrator)
before this pipeline runs — this module simply reads it from the PostRow.
"""

import logging
from dataclasses import dataclass

from config import Config
from dataforseo_client import DataForSEOClient
from perplexity_client import PerplexityClient
from sheets_client import PostRow, SheetsClient

logger = logging.getLogger(__name__)


@dataclass
class ResearchData:
    paa_data: str
    ahrefs_data: str       # Pre-populated by Claude Code MCP before pipeline runs
    perplexity_data: str


class DataGatherer:
    def __init__(self, cfg: Config, sheets: SheetsClient):
        self.cfg = cfg
        self.sheets = sheets
        self.dataforseo = DataForSEOClient(cfg)
        self.perplexity = PerplexityClient(cfg)

    def gather(self, row: PostRow) -> ResearchData:
        """
        Gather all research data for a post.
        DataForSEO and Perplexity are called live.
        Ahrefs data is read from the pre-populated sheet column (populated by Claude MCP).
        """
        keyword = row.target_keyword
        logger.info(f"Gathering research data for: '{keyword}'")

        # --- DataForSEO PAA ---
        logger.info(f"  → DataForSEO PAA...")
        paa_data = self.dataforseo.get_paa(keyword)
        self.sheets.save_paa_data(row, paa_data)

        # --- Ahrefs (pre-populated by Claude Code MCP) ---
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

        # --- Perplexity competitive research ---
        logger.info(f"  → Perplexity competitive analysis...")
        perplexity_data = self.perplexity.get_competitive_analysis(
            post_title=row.post_title,
            target_keyword=keyword,
        )
        self.sheets.save_perplexity_data(row, perplexity_data)

        return ResearchData(
            paa_data=paa_data,
            ahrefs_data=ahrefs_data,
            perplexity_data=perplexity_data,
        )
