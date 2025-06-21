from hashlib import sha256
import inspect
from pathlib import Path
import shutil
import subprocess
import sys

# Third-party
import pytest

# Ensure repo root on path (mirrors style of other integration tests)
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Local imports
from InstanceScrubber.archive_backup import create_backup  # noqa: E402
from InstanceScrubber.archive_manager import ArchiveManager  # noqa: E402


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _create_dummy_wav(path: Path) -> None:  # pragma: no cover – shared helper
    """Write a minimal (header-only) WAV file to *path* for testing."""
    header = (
        b"RIFF"  # Chunk ID
        + (36).to_bytes(4, "little")  # ChunkSize
        + b"WAVE"  # Format
        + b"fmt "  # Subchunk1ID
        + (16).to_bytes(4, "little")  # Subchunk1Size
        + (1).to_bytes(2, "little")  # AudioFormat (PCM)
        + (1).to_bytes(2, "little")  # NumChannels
        + (16000).to_bytes(4, "little")  # SampleRate
        + (16000 * 2).to_bytes(4, "little")  # ByteRate
        + (2).to_bytes(2, "little")  # BlockAlign
        + (16).to_bytes(2, "little")  # BitsPerSample
        + b"data"  # Subchunk2ID
        + (0).to_bytes(4, "little")  # Subchunk2Size – no data
    )
    path.write_bytes(header)


def _file_hash(path: Path) -> str:
    """Return **sha256** hex digest of *path* contents."""
    h = sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Integration test – fulfils DEV_TASKS Task 35.3
# ---------------------------------------------------------------------------


@pytest.fixture()
def temp_archive_root(tmp_path_factory) -> Path:  # noqa: D401 – fixture
    return tmp_path_factory.mktemp("archive_root")


def test_backup_then_restore_cycle(temp_archive_root: Path, tmp_path: Path):
    """End-to-end verification that backup then restore preserves file hashes."""

    # Step 1 – Create dummy sessions ------------------------------------------------------
    manager = ArchiveManager(base_dir=temp_archive_root)

    for idx in range(3):
        wav_path = temp_archive_root / f"dummy_{idx}.wav"
        _create_dummy_wav(wav_path)
        manager.archive(wav_path=wav_path, transcription=f"Sample transcription {idx}")

    # Capture original hashes
    original_hashes = {
        p.relative_to(temp_archive_root): _file_hash(p)
        for p in temp_archive_root.rglob("*")
        if p.is_file()
    }
    assert original_hashes, "Expected at least one file in archive"

    # Step 2 – Create backup ZIP ----------------------------------------------------------
    backup_dir = tmp_path / "backups"
    zip_path = create_backup(temp_archive_root, backup_dir)
    assert zip_path.exists(), "Backup ZIP was not created"

    # Step 3 – Remove the original archive to simulate data loss --------------------------
    shutil.rmtree(temp_archive_root)
    assert not temp_archive_root.exists(), "Archive directory should be removed for restore test"

    # Step 4 – Restore via *CLI* script ---------------------------------------------------
    restore_script = ROOT_DIR / "scripts" / "archive_restore.py"
    restored_root = tmp_path / "restored_archive"

    completed = subprocess.run(  # noqa: S603 – internal call to python
        [sys.executable, str(restore_script), str(zip_path), "--dest", str(restored_root)],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        pytest.fail(
            (
                f"archive_restore.py failed (code {completed.returncode}):\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        )

    # Step 5 – Validate hashes after restore ---------------------------------------------
    restored_hashes = {
        p.relative_to(restored_root): _file_hash(p)
        for p in restored_root.rglob("*")
        if p.is_file()
    }

    assert restored_hashes == original_hashes, (
        "Restored files differ from original.\n"
        f"Original: {len(original_hashes)} files, Restored: {len(restored_hashes)} files"
    ) 