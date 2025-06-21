import inspect
import sys
from pathlib import Path

import pytest

# Ensure repo root on path
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.spooler import AudioSpooler  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch, tmp_path):
    """Redirect *APPDATA* so spooler writes into the pytest temp dir."""
    monkeypatch.setenv("APPDATA", str(tmp_path))


def _write_dummy_chunks(spooler: AudioSpooler, *, count: int = 120):
    """Helper – create *count* sequential chunk files with deterministic data."""
    for idx in range(count):
        # Each chunk holds its 1-byte index repeated *idx+1* times so we can
        # verify exact concatenation ordering.
        byte_val = (idx % 256).to_bytes(1, "little")
        spooler.write_chunk(byte_val * (idx + 1))


def test_merge_120_chunks(tmp_path):
    """All 120 chunks must be merged in order with correct byte length."""
    spooler = AudioSpooler()
    spooler.start_session()

    _write_dummy_chunks(spooler, count=120)

    # Simulate crash – leave files on disk
    spooler.close_session(success=False)

    temp_dir = tmp_path / "Instant Scribe" / "temp"
    assert len(list(temp_dir.glob("chunk_*.pcm"))) == 120

    merged_path = AudioSpooler.merge_chunks(source_dir=temp_dir)
    assert merged_path.exists()

    # Validate size = sum_{i=1}^{120} (i bytes) = n(n+1)/2
    expected_size = 120 * 121 // 2
    assert merged_path.stat().st_size == expected_size

    # Spot-check first and last bytes to ensure ordering preserved
    data = merged_path.read_bytes()
    assert data[0] == 0  # chunk_0001 byte value
    assert data[-1] == 119 % 256  # last chunk byte pattern


def test_merge_cleans_up_option(monkeypatch, tmp_path):
    """When *cleanup=True* the original chunk files should be removed."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    spooler = AudioSpooler()
    spooler.start_session()
    _write_dummy_chunks(spooler, count=3)
    spooler.close_session(success=False)

    temp_dir = tmp_path / "Instant Scribe" / "temp"
    out_file = AudioSpooler.merge_chunks(source_dir=temp_dir, cleanup=True)

    # Only the merged file should remain
    remaining = list(temp_dir.iterdir())
    assert remaining == [out_file] 