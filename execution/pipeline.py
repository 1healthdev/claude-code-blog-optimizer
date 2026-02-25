"""
Blog Optimization Pipeline — main CLI entry point.

Usage:
  python execution/pipeline.py                 # Process all Pending posts
  python execution/pipeline.py --limit 1       # Process only the first Pending post
  python execution/pipeline.py --dry-run       # List Pending posts, no API calls
  python execution/pipeline.py --post-id 123   # Process a specific post ID only

Prerequisites:
  1. pip install -r execution/requirements.txt
  2. Fill in all values in .env
  3. Place 5 knowledge files in knowledge/
  4. Add your optimization prompt to .agent/skills/blog-optimizer/references/content-generation-prompt.md
  5. (Optional) Run Ahrefs MCP pre-step in Claude Code to populate Column S
  6. Set rows to Status="Pending" in the Blog_Optimization_Queue Google Sheet
  7. Run: python execution/pipeline.py
"""

import argparse
import logging
import sys
import traceback
from pathlib import Path

# Ensure execution/ is on the path when run from workspace root
sys.path.insert(0, str(Path(__file__).parent))

from logger import setup_logger
from config import load_config
from sheets_client import SheetsClient, PostRow
from wp_client import WordPressClient
from data_gatherer import DataGatherer
from blog_analyst import BlogAnalyst
from content_generator import ContentGenerator
from docs_client import DocsClient

logger = logging.getLogger(__name__)


def process_post(
    row: PostRow,
    sheets: SheetsClient,
    wp: WordPressClient,
    gatherer: DataGatherer,
    analyst: BlogAnalyst,
    generator: ContentGenerator,
    docs: DocsClient,
    dry_run: bool = False,
) -> bool:
    """
    Run the full pipeline for a single post.
    Returns True on success, False on error.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {row.post_title}")
    logger.info(f"  URL      : {row.post_url}")
    logger.info(f"  Keyword  : {row.target_keyword}")
    logger.info(f"  Category : {row.platform_category}")
    logger.info(f"  Row      : {row.row_number}")

    if dry_run:
        logger.info("  [DRY RUN] Skipping all API calls.")
        return True

    try:
        # Step 1: Mark as DataGathering
        sheets.update_status(row, "DataGathering")

        # Step 2: Fetch current WordPress content
        logger.info("Step 2: Fetching current post content from WordPress...")
        current_content = wp.fetch_post_content(row.post_id)

        # Step 3: Gather research data (DataForSEO + Perplexity + Ahrefs from Sheet)
        logger.info("Step 3: Gathering research data...")
        research = gatherer.gather(row)

        # Step 4: Mark as Optimizing
        sheets.update_status(row, "Optimizing")

        # Step 5: Generate analysis brief
        logger.info("Step 4: Generating analysis brief (Blog_Analyst)...")
        brief = analyst.generate_brief(row, research, current_content)

        # Step 6: Generate full optimized content
        logger.info("Step 5: Generating optimized content (single Claude call)...")
        content = generator.generate(row, research, brief, current_content)

        # Step 7: Create Google Doc
        logger.info("Step 6: Creating Google Doc...")
        doc_url = docs.create_document(row.post_title, content)

        # Step 8: Update Sheet with Doc URL, optimization date, and final status
        sheets.save_doc_url(row, doc_url)
        sheets.save_optimization_date(row)          # Column T — today's date
        sheets.update_status(row, "Awaiting_Review")

        logger.info(f"✓ Completed: {row.post_title}")
        logger.info(f"  Doc: {doc_url}")
        return True

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        logger.error(f"✗ Failed: {row.post_title}\n{error_msg}")
        try:
            sheets.save_error(row, error_msg)
        except Exception as sheet_err:
            logger.error(f"Could not update error status in Sheet: {sheet_err}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Blog Optimization Pipeline — processes posts from Google Sheets queue"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of posts to process (default: all pending)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List pending posts without making any API calls"
    )
    parser.add_argument(
        "--post-id", type=str, default=None,
        help="Process only the post with this WordPress post ID"
    )
    args = parser.parse_args()

    # Load config (validates all .env vars)
    cfg = load_config()
    setup_logger(level=cfg.log_level)

    logger.info("Blog Optimization Pipeline starting...")
    if args.dry_run:
        logger.info("Mode: DRY RUN (no API calls)")
    logger.info(cfg.summary())

    # Initialize clients
    sheets = SheetsClient(cfg)
    wp = WordPressClient(cfg)
    gatherer = DataGatherer(cfg, sheets)
    analyst = BlogAnalyst(cfg)
    generator = ContentGenerator(cfg)
    docs = DocsClient(cfg)

    # Fetch pending posts
    pending_rows = sheets.get_pending_rows()

    if not pending_rows:
        logger.info("No pending posts found. Set rows to Status='Pending' in the Sheet.")
        return

    # Apply filters
    if args.post_id:
        pending_rows = [r for r in pending_rows if r.post_id == args.post_id]
        if not pending_rows:
            logger.error(f"No pending post found with post_id={args.post_id}")
            sys.exit(1)

    if args.limit:
        pending_rows = pending_rows[:args.limit]

    logger.info(f"\nPosts to process: {len(pending_rows)}")
    for r in pending_rows:
        logger.info(f"  [{r.row_number}] {r.post_title} ({r.target_keyword}) [{r.platform_category}]")

    if args.dry_run:
        logger.info("\nDry run complete. No changes made.")
        return

    # Process each post
    results = {"success": 0, "error": 0}
    for row in pending_rows:
        ok = process_post(row, sheets, wp, gatherer, analyst, generator, docs, dry_run=False)
        if ok:
            results["success"] += 1
        else:
            results["error"] += 1

    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Pipeline complete.")
    logger.info(f"  ✓ Success : {results['success']}")
    logger.info(f"  ✗ Errors  : {results['error']}")
    logger.info(f"  Total     : {len(pending_rows)}")

    if results["error"] > 0:
        logger.info("Check Column W (Error_Log) in the Sheet for error details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
