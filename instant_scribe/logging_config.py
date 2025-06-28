"""Logging configuration module.

This module centralises project-wide logging setup. Importing it once
(at application start-up) configures the root logger with:
    • RotatingFileHandler → logs/app.log (size-based rotation)
    • TimedRotatingFileHandler → logs/app.jsonl (daily rotation, JSON Lines format)
    • StreamHandler       → console/stdout for developer visibility

Subsequent imports are no-ops thanks to an idempotent guard.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Prevent double configuration if imported multiple times
_CONFIGURED: bool = False


def setup_logging(
    *,
    log_file: str | os.PathLike[str] = "logs/app.log",
    json_log_file: str | os.PathLike[str] = "logs/app.jsonl",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MiB per file
    backup_count: int = 5,
    json_backup_count: int = 30,  # Keep 30 days of JSON logs
    level: int | str = logging.INFO,
    enable_json_logging: bool = True,
) -> None:
    """Configure the root logger with rotating file, JSON, and console handlers.

    Parameters
    ----------
    log_file: path-like or str
        Destination path for the primary text log file. Intermediate directories
        will be created automatically.
    json_log_file: path-like or str
        Destination path for the JSON Lines log file.
    max_bytes: int
        Rotate the text log file once it exceeds this many bytes. Setting ``0``
        disables rotation (not recommended).
    backup_count: int
        Number of rotated text log files to keep (``app.log.1`` → ``app.log.N``).
    json_backup_count: int
        Number of daily JSON log files to keep.
    level: int | str
        Minimum log level captured by the root logger.
    enable_json_logging: bool
        Whether to enable JSON Lines logging alongside text logging.
    """

    global _CONFIGURED  # noqa: PLW0603 – module-level singleton guard

    if _CONFIGURED:
        return  # already done – silently ignore subsequent calls

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    json_log_path = Path(json_log_file)
    json_log_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Formatters -------------------------------------------------------
    text_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Handlers ---------------------------------------------------------
    # Text log handler (existing functionality)
    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(text_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(text_formatter)

    handlers = [file_handler, console_handler]

    # JSON log handler (Task 54)
    if enable_json_logging:
        try:
            # Import JSON logging components
            from InstanceScrubber.json_logging import setup_json_logging
            json_handler = setup_json_logging(
                log_file=json_log_path,
                backup_count=json_backup_count,
                level=level
            )
            handlers.append(json_handler)
        except ImportError:
            # JSON logging not available, continue with text only
            pass

    # --- Root logger configuration ---------------------------------------
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Add all handlers to root logger
    for handler in handlers:
        root_logger.addHandler(handler)

    # Ensure lower-level libs (e.g., `urllib3`) don't overwhelm output
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _CONFIGURED = True


# Auto-configure when module is imported -----------------------------------
setup_logging() 