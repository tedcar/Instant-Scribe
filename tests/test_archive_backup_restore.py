import shutil
from pathlib import Path

import pytest

from InstanceScrubber.backup_manager import create_backup, restore_backup, hash_directory


@pytest.fixture()
def sample_archive(tmp_path: Path) -> Path:
    """Create a dummy *archive* directory mimicking a couple of session folders."""
    archive_root = tmp_path / "archive"

    # Session 1
    s1 = archive_root / "1_2025-01-01_00-00-00"
    s1.mkdir(parents=True)
    (s1 / "recording.wav").write_bytes(b"wavdata1")
    (s1 / "Hello_world.txt").write_text("Hello world", encoding="utf-8")

    # Session 2
    s2 = archive_root / "2_2025-01-02_00-00-00"
    s2.mkdir(parents=True)
    (s2 / "recording.wav").write_bytes(b"wavdata2")
    (s2 / "Another_session.txt").write_text("Another session", encoding="utf-8")

    return archive_root


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_backup_and_restore_preserves_hashes(sample_archive: Path, tmp_path: Path):
    backup_dest = tmp_path / "backups"
    backup_zip = create_backup(sample_archive, backup_dest)

    # Ensure the ZIP was created where expected
    assert backup_zip.is_file()

    # Calculate hashes before deletion
    original_hashes = hash_directory(sample_archive)

    # Remove the original archive to simulate catastrophic loss
    shutil.rmtree(sample_archive)
    assert not sample_archive.exists()

    # Restore backup into same path
    restore_backup(backup_zip, sample_archive)

    # Verify contents and hashes match
    restored_hashes = hash_directory(sample_archive)
    assert original_hashes == restored_hashes, "File hashes after restore should match original"