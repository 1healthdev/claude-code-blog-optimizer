---
name: blog-optimizer
description: "Optimizes blog posts for SEO and AI citation using a Python pipeline: fetches research data (DataForSEO PAA, Ahrefs via MCP, Perplexity), generates analysis brief via Claude, then generates complete optimized HTML deliverable"
tags: [seo, content-optimization, blog, wordpress, medical, automation]
inputs: [google-sheet-queue, knowledge-files, content-generation-prompt]
---

# Blog Optimizer Skill

## Identity
Runs the full blog optimization pipeline for Dr. Rajarshi Mitra's medical practice website (drrajarshimitra.com). Processes posts from the `Blog_Optimization_Queue` Google Sheet, applies the 5-document optimization framework, and outputs complete optimized deliverables to Google Docs.

## Routing Conditions
Activate when the user asks to:
- Optimize blog posts
- Run the pipeline
- Process pending posts
- Fetch Ahrefs data for posts (Ahrefs MCP pre-step)

## Pre-Step: Ahrefs MCP (Layer 2 — Claude Code only)
Before running `pipeline.py`, fetch Ahrefs keyword data for pending posts using the Ahrefs MCP tool and write results to Column S of the Sheet. Python cannot call the Ahrefs MCP directly — this must be done by the Claude Code agent.

## Core Rules
- Run `execution/pipeline.py` for the main optimization pipeline
- Use `--dry-run` first to verify pending posts before processing
- Use `--limit 1` for first test runs
- Always check that all 5 knowledge files exist in `knowledge/` before running
- Always check that `content-generation-prompt.md` exists in `references/` before running

## Edge Cases
- If Ahrefs data is missing (Column S empty): pipeline continues with warning, brief notes the gap
- If a knowledge file is missing: pipeline warns and continues with available files
- If `content-generation-prompt.md` is missing: pipeline uses fallback prompt and warns
- If output hits `max_tokens`: increase `max_tokens` in `content_generator.py` (current: 32,000; max: 64,000)
- If Google OAuth token expires: delete `token.json` and `token_docs.json`, re-run to re-authenticate
