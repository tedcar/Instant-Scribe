#!/usr/bin/env python3
"""Command-line helper to restore an Instant Scribe *archive backup* ZIP.

Usage
-----
python archive_restore.py <backup_zip_path> [--dest DESTINATION]

When *--dest* is omitted the backup is restored into the default archive
root determined by :pyclass:`InstanceScrubber.archive_manager.ArchiveManager`.

This thin wrapper simply invokes
:pyfunc:`InstanceScrubber.backup_manager.restore_backup`.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from InstanceScrubber.archive_manager import ArchiveManager
from InstanceScrubber.backup_manager import restore_backup


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:  # noqa: D401 – helper
    parser = argparse.ArgumentParser(description="Restore Instant Scribe archive from backup ZIP")
    parser.add_argument("zipfile", type=str, help="Path to the backup .zip file")
    parser.add_argument(
        "--dest",
        "-d",
        type=str,
        default=None,
        help="Destination directory for restoration (defaults to configured archive root)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:  # noqa: D401 – CLI entry point
    args = _parse_args(argv)
    zip_path = Path(args.zipfile).expanduser().resolve()

    if args.dest:
        dest_dir = Path(args.dest).expanduser().resolve()
    else:
        dest_dir = ArchiveManager().base_dir  # pylint: disable=not-callable

    restore_backup(zip_path, dest_dir)
    print(f"✔ Backup successfully restored to '{dest_dir}'.")


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])