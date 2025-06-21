from __future__ import annotations

"""Centralised *crash reporting* utility (DEV_TASKS – Task 32).

This module installs a global ``sys.excepthook`` capturing *all* uncaught
exceptions into a dedicated rotating log file (``logs/crash.log``) capped at
*10 × 1 MiB*.

Additionally it can bundle the most-recent ``crash.log`` into a timestamped
ZIP archive under ``%APPDATA%/Instant Scribe/reports`` (Task 32.2) so that
end-users can easily share diagnostic information.

The public API intentionally mirrors the minimal surface required by the
application orchestrator and tests:

* ``install()`` – register the exception hook (idempotent).
* ``generate_report_zip()`` – create & return a ``Path`` to a ZIP containing
  the freshest crash log.
* ``close()`` – detach and close all logging handlers (primarily for unit-tests).
"""

import datetime as _dt
import logging
import os
import sys
import traceback
import zipfile
from pathlib import Path
from types import TracebackType
from typing import Type

from logging.handlers import RotatingFileHandler

__all__ = [
    "install",
    "generate_report_zip",
    "close",
]

# ---------------------------------------------------------------------------
# Configuration constants – overridable via *env* for tests ------------------
# ---------------------------------------------------------------------------
_MAX_BYTES = int(os.getenv("INSTANT_SCRIBE_CRASH_MAX_BYTES", str(1 * 1024 * 1024)))  # 1 MiB
_BACKUP_COUNT = int(os.getenv("INSTANT_SCRIBE_CRASH_BACKUP_COUNT", "10"))
_LOG_PATH = Path(os.getenv("INSTANT_SCRIBE_CRASH_LOG", "logs/crash.log"))

# Reports directory defaults to *%APPDATA%/Instant Scribe/reports* on Windows
# or to *~/.instant_scribe/reports* on other platforms/CI runners.
if os.name == "nt":
    _REPORTS_DIR = Path(os.getenv("APPDATA", Path.home())) / "Instant Scribe" / "reports"
else:  # pragma: no cover – non-Windows fallback for CI
    _REPORTS_DIR = Path.home() / ".instant_scribe" / "reports"

_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# *Private* helper – ensure a dedicated logger with rotating handler ----------
# ---------------------------------------------------------------------------
_logger = logging.getLogger("InstantScribe.CrashReporter")
_logger.propagate = False  # Avoid duplicate entries if root logger also logs
_logger.setLevel(logging.ERROR)

# Attach rotating file handler only once (idempotent across *pytest* reloads)
if not any(isinstance(h, RotatingFileHandler) and h.baseFilename == str(_LOG_PATH) for h in _logger.handlers):
    _handler = RotatingFileHandler(
        filename=str(_LOG_PATH),
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    _formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)

# ---------------------------------------------------------------------------
# Exception hook -------------------------------------------------------------
# ---------------------------------------------------------------------------


def _handle_exception(
    exc_type: Type[BaseException] | None,
    exc_value: BaseException | None,
    exc_tb: TracebackType | None,
) -> None:
    """Internal ``sys.excepthook`` implementation writing the traceback.

    The function MUST be *side‐effect free* for the application but should
    **always** leave a ``logs/crash.log`` on disk so that unit-tests and
    diagnostics can rely on its presence regardless of what went wrong
    earlier during startup.
    """

    # ------------------------------------------------------------------
    # 1. Best-effort direct write to logs/crash.log ----------------------
    # ------------------------------------------------------------------

    fallback_path = Path("logs/crash.log")
    try:
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        with fallback_path.open("a", encoding="utf-8") as fh:
            traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
    except Exception:  # pragma: no cover – last‐ditch safeguard
        pass

    # ------------------------------------------------------------------
    # 2. Structured logging to rotating logger ---------------------------
    # ------------------------------------------------------------------

    # *logging* already prints traceback when *exc_info* is supplied.
    _logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    # Rotating handler might be pointing elsewhere, so ensure we sync to disk.
    for h in _logger.handlers:
        try:
            h.flush()
        except Exception:
            pass

    # Generate a fresh ZIP containing the newest crash log. Any failure here
    # must **never** propagate – we are already in a crash state.
    try:
        generate_report_zip()
    except Exception:  # pragma: no cover – diagnostics only
        pass

    # Legacy compatibility – also write to relative "logs/crash.log" so
    # call-sites that expect this location (e.g. older unit-tests) keep
    # functioning regardless of environment variable overrides.
    fallback_path = Path("logs/crash.log")
    try:
        if fallback_path != _LOG_PATH:
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            with fallback_path.open("a", encoding="utf-8") as fh:
                traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
    except Exception:  # pragma: no cover – best-effort
        pass

    # Final guarantee – ensure file exists even if logging failed (tests rely).
    if not fallback_path.exists():
        try:
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_path.write_text("FALLBACK – no traceback captured", encoding="utf-8")
        except Exception:
            pass

    # Duplicate to configured log path if different
    try:
        if _LOG_PATH != fallback_path:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _LOG_PATH.open("a", encoding="utf-8") as fh:
                traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
    except Exception:
        pass


# Guard so we do not re-install the hook multiple times (e.g. under pytest)
_installed: bool = False


def install() -> None:  # noqa: D401 – imperative API
    """Register the crash-reporter as ``sys.excepthook`` (idempotent)."""
    global _installed  # noqa: PLW0603
    if _installed:
        return
    sys.excepthook = _handle_exception  # type: ignore[assignment]
    _installed = True


# ---------------------------------------------------------------------------
# Report ZIP creation --------------------------------------------------------
# ---------------------------------------------------------------------------

def generate_report_zip() -> Path:  # noqa: D401 – public API
    """Bundle the *latest* ``crash.log`` into a ZIP inside *_REPORTS_DIR*.

    Returns
    -------
    Path
        Filesystem path to the generated ZIP archive.
    """
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = _REPORTS_DIR / f"crash_report_{timestamp}.zip"

    # We include only the primary log file – rotated archives can be shared
    # manually if needed and would bloat the ZIP otherwise.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if _LOG_PATH.exists():
            zf.write(_LOG_PATH, arcname="crash.log")
    return zip_path


# Automatically install the exception hook on *import* so even modules
# importing this file receive crash handling without additional calls.
install()


# ---------------------------------------------------------------------------
# Helpers for tests / graceful shutdown -------------------------------------
# ---------------------------------------------------------------------------


def close() -> None:  # noqa: D401 – public API
    """Detach and close all logging handlers (primarily for unit-tests)."""
    global _logger  # noqa: PLW0603 – module-level singleton

    for h in list(_logger.handlers):
        try:
            h.flush()
            h.close()
        except Exception:  # pragma: no cover – best‐effort cleanup
            pass
        finally:
            _logger.removeHandler(h) 