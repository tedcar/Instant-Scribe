import inspect
import multiprocessing as mp
from pathlib import Path

import numpy as np
import pytest

# Ensure repo root on sys.path so local imports resolve (esp. for spawned processes)
import sys
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.transcription_worker import (
    TranscriptionEngine,
    TranscriptionWorker,
    EngineResponse,
)  # noqa: E402


@pytest.fixture()
def dummy_audio_array():
    """Return 1-second dummy 16-kHz mono silence as *np.int16* array."""
    return np.zeros(16_000, dtype=np.int16)


def test_engine_plain_and_detailed(dummy_audio_array):
    """Engine should return deterministic outputs via the stub model."""
    engine = TranscriptionEngine()
    engine.load_model(use_stub=True)

    plain = engine.get_plain_transcription(dummy_audio_array)
    assert plain == "hello world"

    detailed_text, timestamps = engine.get_detailed_transcription(dummy_audio_array)
    assert detailed_text.startswith("hello world")
    assert isinstance(timestamps, list)

    rtf = engine.benchmark_rtf(dummy_audio_array)
    assert rtf >= 0  # Any non-negative value acceptable for the stub


def _run_worker(request_q: mp.Queue, response_q: mp.Queue):  # pragma: no cover – spawned helper
    """Spawn-safe adapter calling the real background process entry point."""
    # Import inside the child to avoid pickling issues
    from InstanceScrubber.transcription_worker import _worker_process  # type: ignore  # pylint: disable=import-outside-toplevel

    _worker_process(request_q, response_q, use_stub=True)


def test_worker_ipc_cycle(dummy_audio_array):
    """End-to-end round-trip through the *TranscriptionWorker* facade."""
    audio_bytes = dummy_audio_array.tobytes()

    with TranscriptionWorker(use_stub=True) as worker:
        response = worker.transcribe(audio_bytes, timeout=15)

    assert isinstance(response, EngineResponse)
    assert response.ok is True
    assert response.payload == "hello world" 