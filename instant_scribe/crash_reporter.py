from __future__ import annotations

"""Centralised *crash reporting* utility (DEV_TASKS – Task 32 & 55).

This module installs a global ``sys.excepthook`` capturing *all* uncaught
exceptions into a dedicated rotating log file (``logs/crash.log``) capped at
*10 × 1 MiB*.

Additionally it can bundle the most-recent ``crash.log`` into a timestamped
ZIP archive under ``%APPDATA%/Instant Scribe/reports`` (Task 32.2) so that
end-users can easily share diagnostic information.

Task 55 enhancements:
* Uses ``faulthandler`` to generate minidumps on unhandled exceptions.
* Creates both text crash logs and binary minidumps for comprehensive debugging.

The public API intentionally mirrors the minimal surface required by the
application orchestrator and tests:

* ``install()`` – register the exception hook and faulthandler (idempotent).
* ``generate_report_zip()`` – create & return a ``Path`` to a ZIP containing
  the freshest crash log and minidump.
* ``close()`` – detach and close all logging handlers (primarily for unit-tests).
"""

import datetime as _dt
import faulthandler
import logging
import os
import sys
import traceback
import zipfile
from pathlib import Path
from types import TracebackType
from typing import Type, Optional

from logging.handlers import RotatingFileHandler

from . import portable_mode

__all__ = [
    "install",
    "generate_report_zip",
    "close",
    "generate_minidump",
]

# ---------------------------------------------------------------------------
# Configuration constants – overridable via *env* for tests ------------------
# ---------------------------------------------------------------------------
_MAX_BYTES = int(os.getenv("INSTANT_SCRIBE_CRASH_MAX_BYTES", str(1 * 1024 * 1024)))  # 1 MiB
_BACKUP_COUNT = int(os.getenv("INSTANT_SCRIBE_CRASH_BACKUP_COUNT", "10"))
_LOG_PATH = Path(os.getenv("INSTANT_SCRIBE_CRASH_LOG", "logs/crash.log"))

# Task 55 – Minidump configuration
_MINIDUMP_DIR = Path(os.getenv("INSTANT_SCRIBE_MINIDUMP_DIR", "logs/minidumps"))
_ENABLE_MINIDUMPS = os.getenv("INSTANT_SCRIBE_ENABLE_MINIDUMPS", "true").lower() in ("true", "1", "yes")

# Reports directory – portable mode aware
if portable_mode.is_portable_mode():
    _REPORTS_DIR = portable_mode.get_data_path("reports")
elif os.name == "nt":
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
# Task 55 – Minidump generation ---------------------------------------------
# ---------------------------------------------------------------------------

def generate_minidump(filename: Optional[str] = None) -> Optional[Path]:
    """Generate a minidump using faulthandler.

    Args:
        filename: Optional filename for the minidump. If None, generates
                 a timestamped filename.

    Returns:
        Path to the generated minidump file, or None if generation failed.
    """
    if not _ENABLE_MINIDUMPS:
        return None

    try:
        # Ensure minidump directory exists
        _MINIDUMP_DIR.mkdir(parents=True, exist_ok=True)

        # Generate filename if not provided
        if filename is None:
            timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crash_dump_{timestamp}.dmp"

        minidump_path = _MINIDUMP_DIR / filename

        # Generate minidump using faulthandler
        with open(minidump_path, 'wb') as dump_file:
            faulthandler.dump_traceback(dump_file, all_threads=True)

        return minidump_path

    except Exception as exc:
        # Log error but don't propagate - we're already in a crash state
        try:
            _logger.error("Failed to generate minidump: %s", exc)
        except Exception:
            pass
        return None

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

    # Task 55 – Generate minidump alongside crash log
    minidump_path = None
    try:
        minidump_path = generate_minidump()
        if minidump_path:
            _logger.info("Minidump generated: %s", minidump_path)
    except Exception:  # pragma: no cover – diagnostics only
        pass

    # Generate a fresh ZIP containing the newest crash log and minidump. Any failure here
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
    """Register the crash-reporter as ``sys.excepthook`` and enable faulthandler (idempotent)."""
    global _installed  # noqa: PLW0603
    if _installed:
        return

    # Install exception hook
    sys.excepthook = _handle_exception  # type: ignore[assignment]

    # Task 55 – Enable faulthandler for minidump generation
    if _ENABLE_MINIDUMPS:
        try:
            faulthandler.enable()
            _logger.debug("Faulthandler enabled for minidump generation")
        except Exception as exc:
            _logger.warning("Failed to enable faulthandler: %s", exc)

    _installed = True


# ---------------------------------------------------------------------------
# Report ZIP creation --------------------------------------------------------
# ---------------------------------------------------------------------------

def generate_report_zip() -> Path:  # noqa: D401 – public API
    """Bundle the *latest* ``crash.log`` and minidumps into a ZIP inside *_REPORTS_DIR*.

    Returns
    -------
    Path
        Filesystem path to the generated ZIP archive.
    """
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = _REPORTS_DIR / f"crash_report_{timestamp}.zip"

    # We include the primary log file and the most recent minidump
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Add crash log
        if _LOG_PATH.exists():
            zf.write(_LOG_PATH, arcname="crash.log")

        # Task 55 – Add most recent minidump
        if _MINIDUMP_DIR.exists():
            try:
                # Find the most recent minidump
                minidump_files = list(_MINIDUMP_DIR.glob("*.dmp"))
                if minidump_files:
                    # Sort by modification time, newest first
                    latest_minidump = max(minidump_files, key=lambda f: f.stat().st_mtime)
                    zf.write(latest_minidump, arcname=f"minidump/{latest_minidump.name}")
            except Exception as exc:
                # Log error but continue with ZIP creation
                try:
                    _logger.warning("Failed to include minidump in report ZIP: %s", exc)
                except Exception:
                    pass

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