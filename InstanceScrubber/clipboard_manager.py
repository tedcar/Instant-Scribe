from __future__ import annotations

"""Robust clipboard utilities for *Instant Scribe* (Task 23).

This module centralises all interactions with the system clipboard so that
high-level components (e.g. :pymod:`InstanceScrubber.notification_manager`)
no longer need to depend on :pymod:`pyperclip` directly.  The public API
exposes :func:`copy_with_verification` which guarantees that *payload* ends up
on the clipboard **or** a fallback plain-text file is written to disk.

Design goals (Task 23):
    • Provide a best-effort copy-to-clipboard operation with automatic
      verification round-trip
    • Retry a configurable number of times to work around transient clipboard
      races (common on Windows)
    • Gracefully fall back to writing the *payload* to disk using a filename
      derived from the first seven words when clipboard access is impossible
    • Avoid crashes even for extremely large payloads (≥ 1 billion chars)

The implementation purposefully keeps its dependency footprint minimal – it
relies only on :pypi:`pyperclip` (already used by *notification_manager*) and
standard-library modules.
"""

from pathlib import Path
import logging
import time
import re
import textwrap
import zlib
from typing import Optional

__all__ = ["copy_with_verification"]

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _slugify(text: str, max_words: int = 7, max_len: int = 64) -> str:
    """Convert *text* to a safe filename slug.

    The algorithm:
        1. Split on whitespace and take the first *max_words*
        2. Join using underscores
        3. Strip any character that is not alphanumeric, dash or underscore
        4. Truncate to *max_len* chars to avoid pathological long filenames
    """

    words = re.split(r"\s+", text.strip())[:max_words]
    slug = "_".join(words)
    slug = re.sub(r"[^0-9A-Za-z_-]", "", slug)
    return slug[:max_len] or "clip_fallback"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def copy_with_verification(
    payload: str,
    *,
    max_retries: int = 3,
    retry_delay: float = 0.1,
    fallback_dir: str | Path | None = None,
) -> bool:
    """Copy *payload* to the clipboard and verify round-trip integrity.

    Parameters
    ----------
    payload
        The text that should be placed on the system clipboard.
    max_retries
        Number of re-attempts when either the copy or verification step fails.
    retry_delay
        Delay *(seconds)* between retries – mitigates race conditions with
        aggressive clipboard watchers (e.g. password managers).
    fallback_dir
        Directory where a ``.txt`` fallback file will be written if the
        clipboard cannot be used.  Defaults to the current working directory.

    Returns
    -------
    bool
        *True* when the clipboard now contains *payload*, otherwise *False*
        (indicating that a fallback file has been created).
    """

    # Import *pyperclip* at call time so that unit-tests can monkey-patch or
    # replace the module **after** *clipboard_manager* has been imported.  We
    # purposefully fetch the live reference from *sys.modules* so that tests
    # which overwrite the entry with a stub implementation are honoured even
    # if a real *pyperclip* module was imported earlier during the test run.
    import sys, importlib
    pyperclip = sys.modules.get("pyperclip") or importlib.import_module("pyperclip")

    # ------------------------------------------------------------------
    # Fast-path: nothing to do for empty payload
    # ------------------------------------------------------------------
    if not payload:
        _LOG.debug("Nothing to copy – empty payload")
        return True

    # Transparent optimisation – avoid copying gargantuan strings more than
    # once when the verification strategy can be downgraded to a checksum.
    # However, Task 23 explicitly mentions 1 billion-char stress test so we
    # preserve the existing copy-then-paste approach to keep semantics simple.

    # ------------------------------------------------------------------
    # Pre-compute CRC32 checksum for integrity verification (Task 36)
    # ------------------------------------------------------------------
    try:
        checksum_original: Optional[int] = zlib.crc32(payload.encode("utf-8")) & 0xFFFFFFFF
    except Exception as exc:  # pragma: no cover – extremely unlikely
        _LOG.warning("Failed to compute CRC32 – falling back to string comparison: %s", exc)
        checksum_original = None

    # ------------------------------------------------------------------
    # Attempt clipboard copy with verification loop
    # ------------------------------------------------------------------
    for attempt in range(1, max_retries + 1):
        try:
            pyperclip.copy(payload)
        except pyperclip.PyperclipException as exc:
            _LOG.debug("Clipboard copy failed on attempt %d/%d: %s", attempt, max_retries, exc)
        except Exception as exc:  # pragma: no cover – unexpected runtime error
            _LOG.warning("Unexpected error while copying to clipboard: %s", exc)
        else:
            # Verification phase – some clipboard back-ends complete
            # asynchronously so we include a tiny sleep to give the system
            # time to propagate the data.
            try:
                time.sleep(retry_delay)

                clipboard_contents = pyperclip.paste()

                # ------------------------------------------------------------------
                # Integrity verification using CRC32 (preferred) or full text fallback
                # ------------------------------------------------------------------
                if checksum_original is not None:
                    checksum_clipboard = zlib.crc32(clipboard_contents.encode("utf-8")) & 0xFFFFFFFF
                    if checksum_clipboard == checksum_original:
                        _LOG.debug("Clipboard CRC32 verification succeeded on attempt %d", attempt)
                        return True
                else:  # Fallback path: compare full strings (should be rare)
                    if clipboard_contents == payload:
                        _LOG.debug("Clipboard full-text verification succeeded on attempt %d", attempt)
                        return True

                _LOG.debug("Clipboard verification mismatch on attempt %d", attempt)
            except pyperclip.PyperclipException as exc:
                _LOG.debug("Clipboard paste failed on attempt %d/%d: %s", attempt, max_retries, exc)
        # --- Retry -----------------------------------------------------------------
        if attempt < max_retries:
            time.sleep(retry_delay)

    # ------------------------------------------------------------------
    # Fallback – write payload to disk
    # ------------------------------------------------------------------
    dest_dir = Path(fallback_dir or Path.cwd())
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover – unlikely path
        _LOG.warning("Failed to create fallback directory %s: %s", dest_dir, exc)
        dest_dir = Path.cwd()

    filename = _slugify(payload) + ".txt"
    file_path = dest_dir / filename

    # Guard against overwriting – append a counter if file exists.
    counter = 1
    while file_path.exists():
        file_path = dest_dir / f"{_slugify(payload)}_{counter}.txt"
        counter += 1

    try:
        # Use *write_text* with explicit encoding to avoid OS defaults.
        # To mitigate memory bloat with very large payloads we stream via
        # *write* chunks.
        with file_path.open("w", encoding="utf-8", newline="\n") as handle:
            for chunk in textwrap.wrap(payload, 8192):
                handle.write(chunk)
        _LOG.info("Clipboard unavailable – wrote fallback file: %s", file_path)
    except Exception as exc:  # pragma: no cover – disk write failure
        _LOG.error("Failed to write fallback file %s: %s", file_path, exc)
        return False

    return False 