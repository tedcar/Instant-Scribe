import inspect
import sys
import time
from pathlib import Path

import numpy as np
import pytest

# Ensure repo root on sys.path so local imports resolve
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.batch_transcriber import BatchTranscriber  # noqa: E402


@pytest.fixture()
def dummy_slice_bytes():
    """Return 1-second of 16-kHz mono silence as raw ``bytes`` suitable for the engine."""
    silence = np.zeros(16_000, dtype=np.int16)
    return silence.tobytes()


def test_batch_transcriber_end_to_end(dummy_slice_bytes):
    """Submitting 3× slices (simulating 30-min recording) should finish < 3 s."""
    with BatchTranscriber(use_stub=True, max_workers=3) as bt:
        # Simulate 3 × 10-minute windows – content/size irrelevant for stub.
        for _ in range(3):
            bt.submit_slice(dummy_slice_bytes)

        start = time.perf_counter()
        full_text = bt.finalise(timeout_per_slice=5)
        duration = time.perf_counter() - start

    # *Stub* model returns 'hello world' for every slice – expect three repetitions
    assert full_text == "hello world hello world hello world"

    # Requirement: aggregated transcript available in < 3 s for a 30-min recording
    assert duration < 3, f"Batch transcription too slow: {duration:.2f}s" 