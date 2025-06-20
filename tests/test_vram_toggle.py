import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure repo root on sys.path
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.transcription_worker import (
    TranscriptionWorker,
    EngineResponse,
)


@pytest.fixture()
def dummy_audio_bytes():
    """Return 0.5-second silence encoded as raw 16-bit PCM bytes."""
    arr = np.zeros(8000, dtype=np.int16)  # 0.5 s @ 16 kHz
    return arr.tobytes()


def test_vram_toggle_cycle(dummy_audio_bytes):
    """Full unload → load cycle should succeed (Task 11 regression)."""

    with TranscriptionWorker(use_stub=True) as worker:
        # 1) Baseline transcription succeeds with model loaded by default
        resp1 = worker.transcribe(dummy_audio_bytes, timeout=10)
        assert resp1.ok is True and resp1.payload == "hello world"

        # 2) Unload the model – expect OK response
        uresp = worker.unload_model(timeout=10)
        assert uresp.ok is True and uresp.payload.get("state") == "unloaded"

        # 3) Subsequent transcription must fail due to missing model
        resp2 = worker.transcribe(dummy_audio_bytes, timeout=10)
        assert resp2.ok is False

        # 4) Reload the model and verify transcription works again
        lresp = worker.load_model(timeout=30)
        assert lresp.ok is True and lresp.payload.get("state") == "loaded"

        resp3 = worker.transcribe(dummy_audio_bytes, timeout=10)
        assert resp3.ok is True and resp3.payload == "hello world" 