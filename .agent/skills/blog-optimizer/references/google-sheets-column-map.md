# Google Sheets Column Map — Blog_Optimization_Queue

Full 30-column reference for the pipeline. Ground truth confirmed from CSV export 2026-02-25.

| Col | Letter | Field Name | Written By | Read By | Notes |
|-----|--------|-----------|------------|---------|-------|
| 1  | A  | Post_Title | Human | Pipeline | Required |
| 2  | B  | Post_URL | Human | Pipeline | Required |
| 3  | C  | Post_ID | Human | Pipeline | WordPress post ID (integer as string) |
| 4  | D  | Target_Keyword | Human | Pipeline, Perplexity | Primary keyword for optimization |
| 5  | E  | Secondary_Keywords | Human | ContentGenerator | Comma-separated |
| 6  | F  | Tier | Human | Analyst, Generator | 0=pillar, 1=primary, 2=secondary, 3=supporting |
| 7  | G  | Platform_Category | Human | Pipeline (all) | BING_DOMINANT \| GOOGLE_DOMINANT \| BALANCED |
| 8  | H  | GSC_Impressions | Human / GSC export | ContentGenerator | May be empty — proceed regardless |
| 9  | I  | GSC_Clicks | Human / GSC export | ContentGenerator | May be empty — proceed regardless |
| 10 | J  | GSC_CTR | Human / GSC export | ContentGenerator | May be empty — proceed regardless |
| 11 | K  | GSC_Position | Human / GSC export | ContentGenerator | May be empty — proceed regardless |
| 12 | L  | Bing_Impressions | Human / Bing export | ContentGenerator | May be empty — proceed regardless |
| 13 | M  | Bing_Clicks | Human / Bing export | ContentGenerator | May be empty — proceed regardless |
| 14 | N  | Bing_CTR | Human / Bing export | ContentGenerator | May be empty — proceed regardless |
| 15 | O  | Bing_Position | Human / Bing export | ContentGenerator | May be empty — proceed regardless |
| 16 | P  | Priority_Score | Human / formula | —  | Read-only; not used by pipeline |
| 17 | Q  | Status | **Pipeline** | Pipeline | See status-values.md |
| 18 | R  | PAA_Data | **Pipeline** (DataForSEO) | Analyst, Generator | Written in DataGathering step |
| 19 | S  | Ahrefs_Data | **Claude Code MCP** (pre-step) | Analyst, Generator | Must be populated BEFORE pipeline runs |
| 20 | T  | Optimization_Date | **Pipeline** | — | Written on success (ISO date: YYYY-MM-DD) |
| 21 | U  | Review_Status | Human | — | Read-only; set by human reviewer |
| 22 | V  | WP_Draft_ID / Doc_URL | **Pipeline** | — | Google Doc URL written on success |
| 23 | W  | Error_Log | **Pipeline** (on error) | — | Stack trace; max 50,000 chars |
| 24 | X  | Notes | Human | ContentGenerator | Special instructions for this post |
| 25 | Y  | Section | Human | ContentGenerator | Content section/category |
| 26 | Z  | Post_Type | Human | ContentGenerator | Post type classification |
| 27 | AA | Secondary_Keywords_AI_Suggested | AI / Human | — | Not currently used by pipeline |
| 28 | AB | Description | Human | ContentGenerator | Post description/summary |
| 29 | AC | URL_Slug | Human | — | Not currently used by pipeline |
| 30 | AD | Perplexity_Data | **Pipeline** (Perplexity) | Analyst, Generator | Written in DataGathering step |

---

## ⚠️ Critical Notes

### Ahrefs Pre-Step (Column S)
Ahrefs has no public REST API (enterprise-only). Ahrefs data **must be populated by the Claude Code agent** via the Ahrefs MCP server before `pipeline.py` is run. The pipeline reads Column S as a string — it will warn and continue if empty.

**Pre-step workflow:**
1. Claude Code agent fetches keyword data from Ahrefs MCP
2. Writes results to Column S for each pending row
3. Then run `python execution/pipeline.py`

### GSC/Bing Metrics (Columns H–O)
These are **bonus context**, not requirements. The pipeline is designed to optimize posts even when all metric columns are empty (new posts, low-traffic posts, strategic pre-optimization). **Never treat empty metrics as an error.**

### Make.com Blueprint Notation
The blueprint references columns as `{{10.Column T}}` — this is Make.com's module variable syntax (Module 10's output, field "Column T"). It does **NOT** mean Sheet Column T. Always refer to this map, not the blueprint's module variable names.

### Perplexity Column (AD)
Blueprint Section 2H's output is stored in Column AD (`Perplexity_Data`). The original pipeline code was correct. Confirmed from CSV.

---

## Column Index Reference (0-based)

For Python `_col_idx()` function — useful when debugging:

```
A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9
K=10, L=11, M=12, N=13, O=14, P=15, Q=16, R=17, S=18, T=19
U=20, V=21, W=22, X=23, Y=24, Z=25
AA=26, AB=27, AC=28, AD=29
```
