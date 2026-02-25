"""
Google Sheets client for the blog optimization queue.

Full 30-column map (A–AD) — Blog_Optimization_Queue:
┌────┬──────────────────────────────┬──────────────────────────────────────────┐
│ Col│ Field                        │ Notes                                    │
├────┼──────────────────────────────┼──────────────────────────────────────────┤
│  A │ Post_Title                   │ Read by pipeline                         │
│  B │ Post_URL                     │ Read by pipeline                         │
│  C │ Post_ID                      │ WordPress post ID (int as string)        │
│  D │ Target_Keyword               │ Primary keyword for optimization         │
│  E │ Secondary_Keywords           │ Comma-separated secondary keywords       │
│  F │ Tier                         │ 0=pillar, 1=primary, 2=secondary, 3=supporting │
│  G │ Platform_Category            │ BING_DOMINANT | GOOGLE_DOMINANT | BALANCED│
│  H │ GSC_Impressions              │ Google Search Console (may be empty)     │
│  I │ GSC_Clicks                   │ Google Search Console (may be empty)     │
│  J │ GSC_CTR                      │ Google Search Console (may be empty)     │
│  K │ GSC_Position                 │ Google Search Console (may be empty)     │
│  L │ Bing_Impressions             │ Bing Webmaster Tools (may be empty)      │
│  M │ Bing_Clicks                  │ Bing Webmaster Tools (may be empty)      │
│  N │ Bing_CTR                     │ Bing Webmaster Tools (may be empty)      │
│  O │ Bing_Position                │ Bing Webmaster Tools (may be empty)      │
│  P │ Priority_Score               │ Calculated priority (read-only)          │
│  Q │ Status                       │ Pending → DataGathering → Optimizing     │
│    │                              │   → Awaiting_Review | Error              │
│  R │ PAA_Data                     │ Written by pipeline (DataForSEO)         │
│  S │ Ahrefs_Data                  │ Written by Claude Code MCP pre-step      │
│  T │ Optimization_Date            │ Written by pipeline after completion     │
│  U │ Review_Status                │ Human review status (read-only)          │
│  V │ WP_Draft_ID (Doc URL)        │ Written by pipeline (Google Doc URL)     │
│  W │ Error_Log                    │ Written by pipeline on error             │
│  X │ Notes                        │ Manual notes / special instructions      │
│  Y │ Section                      │ Content section/category                 │
│  Z │ Post_Type                    │ Post type classification                 │
│ AA │ Secondary_Keywords_AI_Suggested │ AI-suggested secondary keywords      │
│ AB │ Description                  │ Post description/summary                 │
│ AC │ URL_Slug                     │ WordPress URL slug                       │
│ AD │ Perplexity_Data              │ Written by pipeline (Perplexity research)│
└────┴──────────────────────────────┴──────────────────────────────────────────┘

Status lifecycle:
  Pending → DataGathering → Optimizing → Awaiting_Review
                                       → Error (any step can set this)
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import Config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Convenience map — human-readable field name → column letter
COLUMN_MAP = {
    "post_title":                    "A",
    "post_url":                      "B",
    "post_id":                       "C",
    "target_keyword":                "D",
    "secondary_keywords":            "E",
    "tier":                          "F",
    "platform_category":             "G",
    "gsc_impressions":               "H",
    "gsc_clicks":                    "I",
    "gsc_ctr":                       "J",
    "gsc_position":                  "K",
    "bing_impressions":              "L",
    "bing_clicks":                   "M",
    "bing_ctr":                      "N",
    "bing_position":                 "O",
    "priority_score":                "P",
    "status":                        "Q",
    "paa_data":                      "R",
    "ahrefs_data":                   "S",
    "optimization_date":             "T",
    "review_status":                 "U",
    "doc_url":                       "V",   # WP_Draft_ID / Doc URL
    "error_log":                     "W",
    "notes":                         "X",
    "section":                       "Y",
    "post_type":                     "Z",
    "secondary_keywords_ai":         "AA",
    "description":                   "AB",
    "url_slug":                      "AC",
    "perplexity_data":               "AD",
}


# Column letter → 0-based index helpers
_COL = {c: i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}


def _col_idx(letter: str) -> int:
    """Convert column letter (A-Z) or two-letter (AA, AB...) to 0-based index."""
    letter = letter.upper()
    if len(letter) == 1:
        return _COL[letter]
    return 26 * (_COL[letter[0]] + 1) + _COL[letter[1]]


@dataclass
class PostRow:
    """Represents a single row from the Blog_Optimization_Queue sheet."""

    row_number: int         # 1-based row number in the sheet (including header)

    # ── Core post identity (always present) ──────────────────────────────────
    post_title: str         # A
    post_url: str           # B
    post_id: str            # C
    target_keyword: str     # D
    platform_category: str  # G — BING_DOMINANT | GOOGLE_DOMINANT | BALANCED
    status: str             # Q

    # ── Research columns (written by pipeline / MCP pre-step) ────────────────
    paa_data: str           # R
    ahrefs_data: str        # S
    perplexity_data: str    # AD

    # ── Output columns ────────────────────────────────────────────────────────
    doc_url: str            # V (WP_Draft_ID / Google Doc URL)
    error_log: str          # W

    # ── Content strategy fields ───────────────────────────────────────────────
    secondary_keywords: str = ""   # E
    tier: str = ""                 # F — 0=pillar, 1=primary, 2=secondary, 3=supporting
    notes: str = ""                # X — manual notes / special instructions
    section: str = ""              # Y — content section/category
    post_type: str = ""            # Z — post type classification
    description: str = ""         # AB — post description/summary

    # ── Google Search Console metrics (may be empty — pipeline proceeds regardless) ──
    gsc_impressions: str = ""      # H
    gsc_clicks: str = ""           # I
    gsc_ctr: str = ""              # J
    gsc_position: str = ""         # K

    # ── Bing Webmaster Tools metrics (may be empty — pipeline proceeds regardless) ──
    bing_impressions: str = ""     # L
    bing_clicks: str = ""          # M
    bing_ctr: str = ""             # N
    bing_position: str = ""        # O


class SheetsClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.spreadsheet_id = cfg.spreadsheet_id
        self.sheet_name = cfg.queue_sheet_name
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service

        creds = None
        token_path = self.cfg.google_token_path
        creds_path = self.cfg.google_credentials_path

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json())

        self._service = build("sheets", "v4", credentials=creds)
        return self._service

    def _range(self, notation: str) -> str:
        return f"'{self.sheet_name}'!{notation}"

    def _get_all_rows(self) -> list[list]:
        service = self._get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=self._range("A:AD"))
            .execute()
        )
        return result.get("values", [])

    def get_pending_rows(self) -> list[PostRow]:
        """Return all rows where Status (col Q) == 'Pending'."""
        all_rows = self._get_all_rows()
        if not all_rows:
            return []

        pending = []
        for i, row in enumerate(all_rows[1:], start=2):  # skip header, 1-based row numbers
            def cell(letter: str, _row=row) -> str:
                idx = _col_idx(letter)
                return _row[idx].strip() if idx < len(_row) else ""

            status = cell("Q")
            if status.strip().lower() != "pending":
                continue

            pending.append(PostRow(
                row_number=i,
                # Core identity
                post_title=cell("A"),
                post_url=cell("B"),
                post_id=cell("C"),
                target_keyword=cell("D"),
                platform_category=cell("G"),
                status=status,
                # Research columns
                paa_data=cell("R"),
                ahrefs_data=cell("S"),
                perplexity_data=cell("AD"),
                # Output columns
                doc_url=cell("V"),
                error_log=cell("W"),
                # Content strategy fields
                secondary_keywords=cell("E"),
                tier=cell("F"),
                notes=cell("X"),
                section=cell("Y"),
                post_type=cell("Z"),
                description=cell("AB"),
                # GSC metrics
                gsc_impressions=cell("H"),
                gsc_clicks=cell("I"),
                gsc_ctr=cell("J"),
                gsc_position=cell("K"),
                # Bing metrics
                bing_impressions=cell("L"),
                bing_clicks=cell("M"),
                bing_ctr=cell("N"),
                bing_position=cell("O"),
            ))

        logger.info(f"Found {len(pending)} pending post(s)")
        return pending

    # ── Write methods ─────────────────────────────────────────────────────────

    def update_status(self, row: PostRow, status: str) -> None:
        self._update_cell(row.row_number, "Q", status)
        logger.info(f"[Row {row.row_number}] Status → {status}")

    def save_paa_data(self, row: PostRow, paa_data: str) -> None:
        self._update_cell(row.row_number, "R", paa_data)

    def save_ahrefs_data(self, row: PostRow, ahrefs_data: str) -> None:
        self._update_cell(row.row_number, "S", ahrefs_data)

    def save_perplexity_data(self, row: PostRow, perplexity_data: str) -> None:
        self._update_cell(row.row_number, "AD", perplexity_data)

    def save_doc_url(self, row: PostRow, doc_url: str) -> None:
        self._update_cell(row.row_number, "V", doc_url)

    def save_optimization_date(self, row: PostRow, date_str: str | None = None) -> None:
        """Write today's date (or supplied date_str) to Column T (Optimization_Date)."""
        value = date_str or date.today().isoformat()   # e.g. "2026-02-25"
        self._update_cell(row.row_number, "T", value)
        logger.info(f"[Row {row.row_number}] Optimization_Date → {value}")

    def save_error(self, row: PostRow, error_msg: str) -> None:
        self._update_cell(row.row_number, "W", error_msg[:50000])  # Sheets cell limit
        self.update_status(row, "Error")

    def _update_cell(self, row_number: int, col_letter: str, value: str) -> None:
        service = self._get_service()
        range_notation = self._range(f"{col_letter}{row_number}")
        service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_notation,
            valueInputOption="RAW",
            body={"values": [[value]]},
        ).execute()
