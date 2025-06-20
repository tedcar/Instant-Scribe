import inspect
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so local imports work when running via `python -m pytest` from subdir
import sys
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.audio_listener import VADAudioGate  # noqa: E402


class _SequenceVad:
    """Stub VAD that returns a pre-defined True/False sequence."""

    def __init__(self, decisions):
        self._iter = iter(decisions)

    def is_speech(self, _frame: bytes, _sample_rate: int) -> bool:  # noqa: D401 – simple stub
        return next(self._iter, False)


@pytest.fixture()
def dummy_frame():
    """Return a 30-ms dummy PCM frame (16 kHz, 16-bit)."""
    sample_rate = 16_000
    frame_duration_ms = 30
    frame_len_samples = int(sample_rate * (frame_duration_ms / 1000))
    return b"\x00\x00" * frame_len_samples  # silence but valid format


def test_vad_gate_triggers_callbacks(monkeypatch, dummy_frame):
    """Sequence of voiced / unvoiced frames should trigger start & end events."""
    # GIVEN a deterministic VAD decision stream
    decisions = [False] * 3 + [True] * 5 + [False] * 3
    stub_vad = _SequenceVad(decisions)

    # Monkeypatch the webrtcvad.Vad class used inside the gate
    import InstanceScrubber.audio_listener as al  # local alias after import to patch
    monkeypatch.setattr(al.webrtcvad, "Vad", lambda _level=2: stub_vad)

    events = []

    def on_start():
        events.append("start")

    def on_end(_buf):
        events.append("end")

    gate = VADAudioGate(
        frame_duration_ms=30,
        silence_threshold_ms=60,  # 2 frames of 30 ms
        on_speech_start=on_start,
        on_speech_end=on_end,
    )

    # WHEN we feed frames corresponding to the decisions list
    for _ in decisions:
        gate.process_frame(dummy_frame)

    # THEN we expect exactly one start and one end event in correct order
    assert events == ["start", "end"] 