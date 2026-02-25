"""
Configuration loader for the blog optimization pipeline.
Reads all required variables from .env and exposes a typed Config object.
Run directly to verify your environment: python execution/config.py
"""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Resolve workspace root (one level up from execution/)
WORKSPACE_ROOT = Path(__file__).parent.parent
ENV_FILE = WORKSPACE_ROOT / ".env"
KNOWLEDGE_DIR = WORKSPACE_ROOT / "knowledge"


def _require(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val or val.startswith("your-"):
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            f"Please set it in {ENV_FILE}"
        )
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


@dataclass
class Config:
    # Google OAuth
    google_credentials_path: Path
    google_token_path: Path

    # Google Sheets
    spreadsheet_id: str
    queue_sheet_name: str

    # WordPress
    wp_site_url: str
    wp_username: str
    wp_api_key: str

    # Anthropic
    anthropic_api_key: str

    # DataForSEO
    dataforseo_login: str
    dataforseo_password: str

    # Perplexity
    perplexity_api_key: str

    # Google Drive output folder (optional — empty means root Drive)
    google_drive_folder_id: str

    # General
    log_level: str
    tmp_dir: Path
    knowledge_dir: Path

    def mask(self, value: str) -> str:
        if len(value) <= 8:
            return "***"
        return value[:4] + "***" + value[-4:]

    def summary(self) -> str:
        lines = [
            "=== Pipeline Configuration ===",
            f"  Spreadsheet ID    : {self.mask(self.spreadsheet_id)}",
            f"  Queue sheet       : {self.queue_sheet_name}",
            f"  WordPress URL     : {self.wp_site_url}",
            f"  WordPress user    : {self.wp_username}",
            f"  Anthropic key     : {self.mask(self.anthropic_api_key)}",
            f"  DataForSEO login  : {self.mask(self.dataforseo_login)}",
            f"  Perplexity key    : {self.mask(self.perplexity_api_key)}",
            f"  Drive folder      : {self.google_drive_folder_id or 'root (no folder set)'}",
            f"  Google creds      : {self.google_credentials_path}",
            f"  Knowledge dir     : {self.knowledge_dir}",
            f"  Tmp dir           : {self.tmp_dir}",
            f"  Log level         : {self.log_level}",
        ]
        return "\n".join(lines)


def load_config() -> Config:
    load_dotenv(ENV_FILE, override=True)

    cfg = Config(
        google_credentials_path=WORKSPACE_ROOT / _optional("GOOGLE_CREDENTIALS_PATH", "credentials.json"),
        google_token_path=WORKSPACE_ROOT / _optional("GOOGLE_TOKEN_PATH", "token.json"),
        spreadsheet_id=_require("SPREADSHEET_ID"),
        queue_sheet_name=_optional("QUEUE_SHEET_NAME", "Blog_Optimization_Queue"),
        wp_site_url=_require("BLOG_SITE_URL"),
        wp_username=_require("BLOG_USERNAME"),
        wp_api_key=_require("BLOG_API_KEY"),
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        dataforseo_login=_require("DATAFORSEO_LOGIN"),
        dataforseo_password=_require("DATAFORSEO_PASSWORD"),
        perplexity_api_key=_require("PERPLEXITY_API_KEY"),
        google_drive_folder_id=_optional("GOOGLE_DRIVE_OUTPUT_FOLDER_ID", ""),
        log_level=_optional("LOG_LEVEL", "INFO"),
        tmp_dir=WORKSPACE_ROOT / _optional("TMP_DIR", ".tmp"),
        knowledge_dir=KNOWLEDGE_DIR,
    )

    cfg.tmp_dir.mkdir(exist_ok=True)
    return cfg


if __name__ == "__main__":
    # Quick validation — run: python execution/config.py
    sys.path.insert(0, str(WORKSPACE_ROOT / "execution"))
    from logger import setup_logger
    setup_logger()
    try:
        cfg = load_config()
        print(cfg.summary())
        print("\n✓ All required environment variables are set.")
    except EnvironmentError as e:
        print(f"\n✗ Configuration error:\n  {e}", file=sys.stderr)
        sys.exit(1)
