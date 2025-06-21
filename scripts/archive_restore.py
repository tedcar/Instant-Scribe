import argparse
import logging
import sys

# Ensure project root is importable when the script is executed directly.
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.archive_backup import restore_backup


def main() -> None:  # noqa: D401 – CLI entrypoint
    """Command-line utility restoring an *Instant Scribe* archive backup.

    Usage
    -----
    python archive_restore.py <backup_zip> [--dest DEST]
    """

    parser = argparse.ArgumentParser(
        description="Restore an Instant Scribe archive backup ZIP into the canonical folder structure.",
    )
    parser.add_argument(
        "backup_zip",
        help="Path to the .zip backup file created by the backup utility.",
    )
    parser.add_argument(
        "--dest",
        metavar="DEST_DIR",
        help=(
            "Destination directory for the restored archive. "
            "Defaults to the canonical archive root if omitted."
        ),
    )

    args = parser.parse_args()

    try:
        restored_dir = restore_backup(args.backup_zip, args.dest)
        print(f"Backup restored to: {restored_dir}")
    except Exception as exc:  # noqa: BLE001 – present full error to CLI user
        logging.error("Restore failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main() 