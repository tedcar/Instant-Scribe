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
    def __init__(self, *, chunk_interval_sec: int | None = None) -> None:  # noqa: D401 – simple ctor
        """Create a new *AudioSpooler* instance.

        Parameters
        ----------
        chunk_interval_sec
            Desired *chunk interval* in **seconds**.  When *None* the default
            60-second value defined by Task&nbsp;24 is used.  The argument is
            accepted for forward-compatibility – current implementation writes
            one file per :py:meth:`write_chunk` invocation but storing the
            interval now means the API remains stable when future work adds
            time-based rotation.
        """
        self._temp_dir: Path = self._get_temp_dir()
        self._counter: int = 0
        self._active: bool = False
        # Task 24 – configurable chunk interval (seconds)
        self._chunk_interval_sec: int = int(chunk_interval_sec or 60)

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
    # Recovery helpers (Task 24)
    # ------------------------------------------------------------------
    @classmethod
    def merge_chunks(
        cls,
        *,
        source_dir: Path | None = None,
        destination: Path | None = None,
        cleanup: bool = False,
    ) -> Path:  # noqa: D401 – utility API
        """Merge sequential ``chunk_*.pcm`` files into a single output file.

        Parameters
        ----------
        source_dir
            Directory containing the chunk files.  Defaults to the canonical
            temp spool directory.
        destination
            Desired output *Path*.  If *None* a file named ``merged.pcm`` will
            be created in *source_dir*.
        cleanup
            When *True* the individual chunk files are deleted **after** a
            successful merge – this mirrors the recovery workflow where the
            temporary files are no longer needed once reconstructed.

        Returns
        -------
        Path
            The *Path* to the created merged file.
        """
        src = source_dir or cls._get_temp_dir()
        if not src.exists():
            raise FileNotFoundError(f"Source directory does not exist: {src}")

        # Discover chunk files and sort by their numeric index to preserve
        # recording order.
        chunk_files = sorted(src.glob("chunk_*.pcm"), key=cls._sort_key)
        if not chunk_files:
            raise FileNotFoundError("No chunk files found to merge")

        dest_path = destination or src / "merged.pcm"
        # Concatenate using buffered reads to avoid loading all data into RAM.
        with dest_path.open("wb") as out_fh:
            for file in chunk_files:
                with file.open("rb") as in_fh:
                    shutil.copyfileobj(in_fh, out_fh, length=64 * 1024)

        if cleanup:
            for file in chunk_files:
                try:
                    file.unlink(missing_ok=True)  # type: ignore[arg-type]
                except Exception:  # pragma: no cover – best-effort clean-up
                    pass
        return dest_path

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

    @staticmethod
    def _sort_key(path: Path) -> int:  # noqa: D401 – helper
        """Return numeric index extracted from *chunk_XXXX.pcm* name for sorting."""
        stem = path.stem  # e.g. 'chunk_0012'
        try:
            return int(stem.split("_")[1])
        except (IndexError, ValueError):
            # Fallback ensures non-conformant files are sorted last but kept
            return 0x7FFF_FFFF 