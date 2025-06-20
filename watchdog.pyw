"""GUI-less launcher that delegates to *watchdog.py*.

PyInstaller will mark this as the entry‐point when a console window must be
suppressed.  It simply imports :pymod:`watchdog` and invokes its ``main``.
"""
from __future__ import annotations

import sys

# Re‐export watchdog main ----------------------------------------------------
from watchdog import main as _main  # type: ignore  # noqa: WPS433 – runtime import


if __name__ == "__main__":  # pragma: no cover – manual launch only
    _main(sys.argv[1:]) 