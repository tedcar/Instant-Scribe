"""Logging configuration module.

This module centralises project-wide logging setup. Importing it once
(at application start-up) configures the root logger with:
    • RotatingFileHandler → logs/app.log (size-based rotation)
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
    max_bytes: int = 10 * 1024 * 1024,  # 10 MiB per file
    backup_count: int = 5,
    level: int | str = logging.INFO,
) -> None:
    """Configure the root logger with a rotating file + console handler.

    Parameters
    ----------
    log_file: path-like or str
        Destination path for the primary log file. Intermediate directories
        will be created automatically.
    max_bytes: int
        Rotate the log file once it exceeds this many bytes. Setting ``0``
        disables rotation (not recommended).
    backup_count: int
        Number of rotated log files to keep (``app.log.1`` → ``app.log.N``).
    level: int | str
        Minimum log level captured by the root logger.
    """

    global _CONFIGURED  # noqa: PLW0603 – module-level singleton guard

    if _CONFIGURED:
        return  # already done – silently ignore subsequent calls

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Formatters -------------------------------------------------------
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Handlers ---------------------------------------------------------
    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # --- Root logger configuration ---------------------------------------
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handler classes if someone calls setup_logging twice
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Ensure lower-level libs (e.g., `urllib3`) don't overwhelm output
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _CONFIGURED = True


# Auto-configure when module is imported -----------------------------------
setup_logging() 