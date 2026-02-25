# Status Values — Blog_Optimization_Queue (Column Q)

The `Status` field (Column Q) is the pipeline's state machine. The pipeline reads `Pending` rows and updates status at each step.

## Status Lifecycle

```
[Human sets]         [Pipeline]                    [Human sets]
  Pending  ──────→  DataGathering  ──────→  Optimizing  ──────→  Awaiting_Review
                                                                        │
                         ↓ (any step can fail)                         │
                       Error  ←───────────────────────────────────────┘
                                                              (human can reset to Pending)
```

## All Status Values

| Status | Set By | Meaning |
|--------|--------|---------|
| `Pending` | **Human** | Post is queued for optimization. Pipeline will pick it up. |
| `DataGathering` | **Pipeline** | Pipeline has started. DataForSEO PAA + Perplexity are being fetched. |
| `Optimizing` | **Pipeline** | Research data gathered. Claude is generating the analysis brief and content. |
| `Awaiting_Review` | **Pipeline** | Optimization complete. Google Doc URL written to Column V. Human should review. |
| `Approved` | **Human** | Human reviewer has approved the content. Ready for WordPress publish. |
| `Published` | **Human** | Content has been published to WordPress. |
| `Error` | **Pipeline** | An error occurred at any step. Check Column W (Error_Log) for details. Reset to `Pending` to retry. |
| `Skip` | **Human** | Post should be skipped by the pipeline (not `Pending` — will not be picked up). |

## Pipeline Read Logic

```python
# pipeline.py — get_pending_rows()
if status.strip().lower() != "pending":
    continue  # skips all other status values
```

Only rows with exactly `Pending` (case-insensitive) are processed.

## Error Recovery

If a post hits `Error` status:
1. Check Column W (Error_Log) for the full Python stack trace
2. Fix the underlying issue (API key, network, missing data, etc.)
3. Clear Column W (optional)
4. Reset Column Q back to `Pending`
5. Re-run the pipeline

## Colors (Make.com Blueprint Reference)

The blueprint uses color-coding for visual tracking in Google Sheets:
- 🟡 `Pending` — Yellow
- 🔵 `DataGathering` — Blue
- 🟠 `Optimizing` — Orange
- 🟢 `Awaiting_Review` — Green
- ✅ `Approved` — Dark Green
- 🔴 `Error` — Red
- ⚫ `Skip` — Gray

Colors are cosmetic only and not enforced by the pipeline. Apply manually via conditional formatting if desired.
