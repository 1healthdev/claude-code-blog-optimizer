"""
Google Docs client — creates the output document for each optimized post.

The document is created in the root of Google Drive by default.
Returns the document URL for storage in the Google Sheet (Column V).
"""

import logging
from datetime import date

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import Config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",   # full Drive access needed to create in user folders
]


class DocsClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._docs_service = None
        self._drive_service = None

    def _get_credentials(self) -> Credentials:
        creds = None
        token_path = self.cfg.google_token_path
        creds_path = self.cfg.google_credentials_path

        # Docs needs different scopes than Sheets — use a separate token file
        token_path_docs = token_path.parent / "token_docs.json"

        if token_path_docs.exists():
            creds = Credentials.from_authorized_user_file(str(token_path_docs), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            token_path_docs.write_text(creds.to_json())

        return creds

    def _get_docs_service(self):
        if not self._docs_service:
            creds = self._get_credentials()
            self._docs_service = build("docs", "v1", credentials=creds)
        return self._docs_service

    def _get_drive_service(self):
        if not self._drive_service:
            creds = self._get_credentials()
            self._drive_service = build("drive", "v3", credentials=creds)
        return self._drive_service

    def create_document(self, post_title: str, content: str) -> str:
        """
        Create a new Google Doc with the optimized post content.
        Creates directly in the configured Drive folder (GOOGLE_DRIVE_OUTPUT_FOLDER_ID).
        Falls back to Drive root if no folder is configured.
        Returns the document URL.
        """
        today = date.today().isoformat()
        doc_title = f"{post_title} — Optimized {today}"

        # Use Drive API to create the file so we can specify the parent folder.
        # The Docs API `documents().create()` does not support parent folders.
        drive = self._get_drive_service()
        file_metadata = {
            "name": doc_title,
            "mimeType": "application/vnd.google-apps.document",
        }
        folder_id = self.cfg.google_drive_folder_id
        if folder_id:
            file_metadata["parents"] = [folder_id]

        file = drive.files().create(body=file_metadata, fields="id").execute()
        doc_id = file["id"]
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

        # Populate with content using the Docs API
        docs = self._get_docs_service()
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
        ).execute()

        logger.info(f"Google Doc created: {doc_title}")
        if folder_id:
            logger.info(f"  Folder: https://drive.google.com/drive/folders/{folder_id}")
        logger.info(f"  URL: {doc_url}")
        return doc_url
