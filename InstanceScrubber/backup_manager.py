from __future__ import annotations

"""Automated ZIP backup & restore utilities for the Instant Scribe *session archive*.

Fulfils *DEV_TASKS.md – Task 35* requirements:
1. **35.1** Periodically create timestamped ZIP snapshots of the archive directory in a
   user-defined destination.
2. **35.2** Provide programmatic helpers that can be consumed by a thin CLI wrapper
   (`archive_restore.py`) to restore a backup into the canonical folder
   structure used by :pyclass:`InstanceScrubber.archive_manager.ArchiveManager`.
3. **35.3** Facilitate integration tests verifying hash equality after a
   backup-then-restore cycle.

The implementation purposefully avoids third-party dependencies to minimise the
runtime footprint.  Scheduling is handled by a lightweight *daemon* thread that
sleeps for the configured interval.
"""

from pathlib import Path
from datetime import datetime
import hashlib
import logging
import shutil
import threading
import time
import zipfile
from typing import Dict, Final

__all__ = [
    "BackupManager",
    "create_backup",
    "restore_backup",
    "hash_directory",
]


class BackupManager:  # pylint: disable=too-few-public-methods
    """Background thread that creates periodic ZIP snapshots of *archive_dir*.

    It is intended to be instantiated by the main application once on startup
    and lives for the lifetime of the process (daemon thread).
    """

    _ZIP_PREFIX: Final[str] = "archive_backup_"
    _TIMESTAMP_FMT: Final[str] = "%Y-%m-%d_%H-%M-%S"

    def __init__(
        self,
        archive_dir: str | Path,
        dest_dir: str | Path,
        *,
        interval_hours: int | float = 24,
        logger: logging.Logger | None = None,
    ) -> None:
        self.archive_dir: Path = Path(archive_dir).expanduser().resolve()
        self.dest_dir: Path = Path(dest_dir).expanduser().resolve()
        self.interval_sec: int = int(max(interval_hours, 1) * 3600)
        self._log = logger or logging.getLogger(self.__class__.__name__)

        if not self.archive_dir.exists():
            raise FileNotFoundError(f"Archive directory does not exist: {self.archive_dir}")
        self.dest_dir.mkdir(parents=True, exist_ok=True)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def start(self, *, daemon: bool = True) -> None:
        """Start the periodic backup thread (returns immediately)."""
        if self._thread and self._thread.is_alive():
            return  # Already running
        self._thread = threading.Thread(target=self._run_loop, daemon=daemon)
        self._thread.start()
        self._log.debug("Backup thread started (interval=%s sec)", self.interval_sec)

    def stop(self, timeout: float | None = 5) -> None:  # noqa: D401 – imperative API
        """Signal the thread to exit and optionally *join* it (max *timeout* seconds)."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=timeout)
            self._log.debug("Backup thread stopped")

    # ------------------------------------------------------------------
    def _run_loop(self) -> None:  # pragma: no cover – trivial while-loop
        """Worker loop executing backups until :pymeth:`stop` is called."""
        # Trigger first backup immediately so users have protection from the get-go.
        next_run = time.time()
        while not self._stop_event.is_set():
            now = time.time()
            if now >= next_run:
                try:
                    self._backup_once()
                except Exception as exc:  # pragma: no cover – defensive belt & braces
                    self._log.error("Backup failed: %s", exc, exc_info=False)
                next_run = now + self.interval_sec
            # Sleep in short increments so we can respond to stop quickly.
            self._stop_event.wait(timeout=1)

    # ------------------------------------------------------------------
    def _backup_once(self) -> Path:
        """Create a single ZIP snapshot and return the path to the file."""
        timestamp = datetime.now().strftime(self._TIMESTAMP_FMT)
        zip_name = f"{self._ZIP_PREFIX}{timestamp}.zip"
        zip_path = self.dest_dir / zip_name

        self._log.info("Creating archive backup → %s", zip_path)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in self.archive_dir.rglob("*"):
                if path.is_file():
                    arcname = path.relative_to(self.archive_dir)
                    zf.write(path, arcname)
        self._log.debug("Backup complete (%d bytes)", zip_path.stat().st_size)
        return zip_path


# ---------------------------------------------------------------------------
# Stand-alone helper functions (simplify unit tests / CLI usage)
# ---------------------------------------------------------------------------

def create_backup(archive_dir: str | Path, dest_dir: str | Path) -> Path:
    """Synchronous helper – create a *one-off* ZIP backup and return its path."""
    manager = BackupManager(archive_dir, dest_dir, interval_hours=24)
    return manager._backup_once()  # type: ignore[attr-defined] – private use intentional


def restore_backup(zip_path: str | Path, dest_dir: str | Path) -> None:
    """Extract *zip_path* into *dest_dir*, replacing any existing content."""
    zip_path = Path(zip_path).expanduser().resolve()
    dest_dir = Path(dest_dir).expanduser().resolve()

    if not zip_path.is_file():
        raise FileNotFoundError(f"Backup ZIP not found: {zip_path}")

    # Remove existing directory to ensure a clean restore (optional design choice)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)


# ---------------------------------------------------------------------------
# Utility – hashing (used by tests to verify integrity)
# ---------------------------------------------------------------------------

def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_directory(root: str | Path) -> Dict[str, str]:
    """Return mapping of *relative file path* → *sha256* for every file under *root*."""
    root_path = Path(root).expanduser().resolve()
    hashes: Dict[str, str] = {}
    for file_path in root_path.rglob("*"):
        if file_path.is_file():
            rel = str(file_path.relative_to(root_path))
            hashes[rel] = _file_sha256(file_path)
    return hashes