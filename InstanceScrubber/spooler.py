"""Persistent audio spooler – fulfils DEV_TASKS.md Task 12 (Never Lose a Word).

The *AudioSpooler* writes sequentially numbered PCM chunks to a temporary
folder under the user's *APPDATA* directory (or a cross-platform fallback).
Its primary goal is to guarantee that no captured audio is lost in the event
of an unexpected application crash.  Upon clean shutdown the temporary files
are removed.  If the application starts and finds leftover chunk files it can
prompt the user to recover the recording.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Final

__all__ = [
    "AudioSpooler",
]


class AudioSpooler:  # pylint: disable=too-few-public-methods
    """Light-weight helper that appends numbered ``.pcm`` files to disk.

    The implementation purposefully avoids any external dependencies so that
    unit-tests can exercise the full code-path in *any* CI environment.
    """

    _CHUNK_TEMPLATE: Final[str] = "chunk_{idx:04d}.pcm"
    _APP_NAME: Final[str] = "Instant Scribe"

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def __init__(self) -> None:  # noqa: D401 – simple ctor
        self._temp_dir: Path = self._get_temp_dir()
        self._counter: int = 0
        self._active: bool = False

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def start_session(self) -> None:  # noqa: D401 – imperative API
        """Create the temp directory (if missing) and reset counter."""
        if self._active:
            # Session already in progress – no-op.
            return

        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0
        self._active = True

    def write_chunk(self, audio_bytes: bytes) -> None:  # noqa: D401 – imperative API
        """Write *audio_bytes* to the next sequential ``chunk_NNNN.pcm`` file."""
        if not self._active:
            # Automatically start a session if the caller forgot to.
            self.start_session()

        self._counter += 1
        file_path = self._temp_dir / self._CHUNK_TEMPLATE.format(idx=self._counter)
        file_path.write_bytes(audio_bytes)

    def close_session(self, *, success: bool = True) -> None:  # noqa: D401 – imperative API
        """Close the current session.

        Parameters
        ----------
        success
            When *True* the temporary chunk files are deleted.  If *False* (e.g.
            on crash) the files remain on disk so they can be recovered on the
            next application start-up.
        """
        if not self._active:
            return

        if success:
            # Best-effort cleanup – ignore errors so shutdown never fails.
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:  # pragma: no cover – defensive
                pass

        self._active = False
        self._counter = 0

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------
    @classmethod
    def incomplete_session_exists(cls) -> bool:  # noqa: D401 – predicate helper
        """Return *True* when un-cleaned chunk files exist on disk."""
        temp_dir = cls._get_temp_dir()
        return any(temp_dir.glob("chunk_*.pcm"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @classmethod
    def _get_temp_dir(cls) -> Path:
        """Return the *Path* to the canonical temporary spool directory."""
        appdata = os.getenv("APPDATA")  # Windows hosts
        if appdata:
            base = Path(appdata)
        else:
            # Cross-platform fallback so tests pass on Linux/macOS runners.
            base = Path(tempfile.gettempdir())
        return base / cls._APP_NAME / "temp" 