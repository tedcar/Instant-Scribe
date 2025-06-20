import inspect
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so local imports work when running via `python -m pytest` from subdir
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.spooler import AudioSpooler  # noqa: E402


def test_spooler_write_and_cleanup(tmp_path, monkeypatch):
    """Chunks should be written sequentially then cleaned on close_session()."""
    # Redirect APPDATA to temporary directory so we do not touch real user files
    monkeypatch.setenv("APPDATA", str(tmp_path))

    spooler = AudioSpooler()
    spooler.start_session()

    # Write three dummy chunks of varying sizes
    spooler.write_chunk(b"a" * 10)
    spooler.write_chunk(b"b" * 20)
    spooler.write_chunk(b"c" * 30)

    temp_dir = tmp_path / "Instant Scribe" / "temp"
    files = sorted(temp_dir.glob("chunk_*.pcm"))
    assert [f.name for f in files] == [
        "chunk_0001.pcm",
        "chunk_0002.pcm",
        "chunk_0003.pcm",
    ]

    # Verify file sizes match payload sizes
    sizes = [f.stat().st_size for f in files]
    assert sizes == [10, 20, 30]

    # Cleanup removes the directory completely
    spooler.close_session(success=True)
    assert not temp_dir.exists()


def test_incomplete_detection(tmp_path, monkeypatch):
    """Static helper should detect leftover chunk files."""
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # Manually create a leftover chunk file
    leftover_dir = tmp_path / "Instant Scribe" / "temp"
    leftover_dir.mkdir(parents=True, exist_ok=True)
    (leftover_dir / "chunk_0001.pcm").write_bytes(b"oops")

    assert AudioSpooler.incomplete_session_exists() is True 