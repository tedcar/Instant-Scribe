"""Archive backup & restore utilities – fulfils *DEV_TASKS.md – Task 35*.

This module provides two primary public functions:

* ``create_backup`` – Compress the complete *session archive* directory (as used by
  :pyclass:`InstanceScrubber.archive_manager.ArchiveManager`) into a time-stamped
  ``.zip`` file at a user-defined backup location.
* ``restore_backup`` – Extract a previously created backup *ZIP* into the canonical
  archive folder structure.

The implementation relies **only** on Python's standard-library to keep the
package footprint minimal and portable.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from InstanceScrubber.archive_manager import ArchiveManager

__all__ = [
    "create_backup",
    "restore_backup",
    "schedule_periodic_backup",
]

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core functionality
# ---------------------------------------------------------------------------

def create_backup(
    archive_root: Path | str | None = None,
    backup_dest_dir: Path | str | None = None,
    *,
    zip_name: str | None = None,
) -> Path:
    """Create a *ZIP* backup of **archive_root** and return the resulting file *Path*.

    Parameters
    ----------
    archive_root:
        Root directory that contains the Instant Scribe *session* folders.  If
        *None*, the default path used by :pyclass:`ArchiveManager` is assumed.
    backup_dest_dir:
        Directory where the backup zip should be written. If *None*, the backup
        is stored **one level above** ``archive_root`` in ``backups``.
    zip_name:
        Optional explicit filename (should include ``.zip`` extension). If *None*,
        a timestamped default (``archive_backup_YYYYMMDD_HHMMSS.zip``) is used.
    """

    # Resolve paths and sensible defaults -------------------------------------------------
    if archive_root is None:
        archive_root = ArchiveManager().base_dir
    archive_root = Path(archive_root).expanduser().resolve()

    if backup_dest_dir is None:
        backup_dest_dir = archive_root.parent / "backups"
    backup_dest_dir = Path(backup_dest_dir).expanduser().resolve()
    backup_dest_dir.mkdir(parents=True, exist_ok=True)

    if zip_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"archive_backup_{timestamp}.zip"

    zip_path = backup_dest_dir / zip_name

    _LOG.info("Creating archive backup → %s", zip_path)

    # Create ZIP – store *relative* paths so restoration does not depend on absolute dirs
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in archive_root.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(archive_root)
                zf.write(file_path, arcname=relative_path)

    _LOG.info("Backup completed successfully – size=%d bytes", zip_path.stat().st_size)
    return zip_path


# ...........................................................................

def restore_backup(
    backup_zip: Path | str,
    dest_root: Path | str | None = None,
) -> Path:
    """Restore an *Instant Scribe* archive backup.

    Parameters
    ----------
    backup_zip:
        Path to the ``.zip`` file created by :pyfunc:`create_backup`.
    dest_root:
        Target root directory where the archive should be restored. If *None*,
        defaults to the canonical location used by :pyclass:`ArchiveManager`.

    Returns
    -------
    Path
        The *dest_root* directory containing the restored sessions.
    """

    backup_zip = Path(backup_zip).expanduser().resolve()

    if not backup_zip.is_file():
        raise FileNotFoundError(f"Backup ZIP not found: {backup_zip}")

    if dest_root is None:
        dest_root = ArchiveManager().base_dir
    dest_root = Path(dest_root).expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    _LOG.info("Restoring backup %s → %s", backup_zip, dest_root)

    with ZipFile(backup_zip, "r") as zf:
        zf.extractall(path=dest_root)

    _LOG.info("Restore complete – extracted %d files", len(zf.namelist()))
    return dest_root


# ---------------------------------------------------------------------------
# Optional periodic scheduler (simple, in-process)
# ---------------------------------------------------------------------------

def _periodic_worker(
    archive_root: Path,
    backup_dir: Path,
    interval: timedelta,
    stop_event: threading.Event,
) -> None:
    """Internal loop that performs backups every *interval* until *stop_event*."""
    next_run = datetime.now()
    while not stop_event.is_set():
        now = datetime.now()
        if now >= next_run:
            try:
                create_backup(archive_root, backup_dir)
            except Exception as exc:  # pragma: no cover – logging only
                _LOG.exception("Scheduled backup failed: %s", exc)
            next_run = now + interval
        stop_event.wait(1)  # poll every second for graceful shutdown


def schedule_periodic_backup(
    *,
    archive_root: Path | str | None = None,
    backup_dest_dir: Path | str | None = None,
    interval_hours: int = 24,
) -> threading.Event:
    """Start a background *thread* that performs backups every *interval_hours*.

    Returns
    -------
    threading.Event
        A *stop_event* that can be set to gracefully terminate the scheduler.
    """

    if archive_root is None:
        archive_root = ArchiveManager().base_dir
    archive_root = Path(archive_root).expanduser().resolve()

    if backup_dest_dir is None:
        backup_dest_dir = archive_root.parent / "backups"
    backup_dest_dir = Path(backup_dest_dir).expanduser().resolve()

    interval_td = timedelta(hours=max(1, interval_hours))

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_periodic_worker,
        args=(archive_root, backup_dest_dir, interval_td, stop_event),
        name="ArchiveBackupScheduler",
        daemon=True,
    )
    thread.start()

    _LOG.info(
        "Started periodic archive backup – every %.1f h to %s",
        interval_td.total_seconds() / 3600.0,
        backup_dest_dir,
    )

    return stop_event


# ---------------------------------------------------------------------------
# CLI entry-point helpers
# ---------------------------------------------------------------------------

def _cli():  # noqa: D401 – imperative CLI helper
    """Tiny CLI wrapper for ad-hoc *create* / *restore* actions."""

    import argparse

    parser = argparse.ArgumentParser(description="Instant Scribe archive backup utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-backup sub-command ------------------------------------------------
    create_p = subparsers.add_parser("create", help="Create a new archive backup ZIP")
    create_p.add_argument("archive_root", nargs="?", help="Path to archive root (defaults to canonical)")
    create_p.add_argument("backup_dest", nargs="?", help="Directory to place ZIP (defaults to <archive>/../backups)")

    # restore sub-command ------------------------------------------------------
    restore_p = subparsers.add_parser("restore", help="Restore archive from backup ZIP")
    restore_p.add_argument("backup_zip", help="Path to backup ZIP file")
    restore_p.add_argument("dest_root", nargs="?", help="Destination archive root (defaults to canonical)")

    args = parser.parse_args()

    if args.command == "create":
        zip_path = create_backup(args.archive_root, args.backup_dest)
        print(zip_path)
    elif args.command == "restore":
        restore_backup(args.backup_zip, args.dest_root)
    else:  # pragma: no cover – safeguard
        parser.error("Unknown command")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _cli() 