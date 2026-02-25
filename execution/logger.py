"""
Logging setup for the blog optimization pipeline.
Call setup_logger() once at startup; all other modules use logging.getLogger(__name__).
"""

import logging
import os
import sys
from pathlib import Path


def setup_logger(level: str = "INFO", log_to_file: bool = False) -> logging.Logger:
    """Configure root logger with console output and optional file output."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Avoid adding duplicate handlers on repeated calls
    if root.handlers:
        return root

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Optional file handler — writes to .tmp/pipeline.log
    if log_to_file:
        log_dir = Path(__file__).parent.parent / ".tmp"
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    return root
