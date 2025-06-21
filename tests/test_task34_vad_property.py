from __future__ import annotations

"""Task 34 – Property-based tests for VAD gate edge cases (Hypothesis).

This test validates that the VAD finite-state-machine implemented by
:class:`InstanceScrubber.audio_listener.VADAudioGate` never emits an *end*
callback without a preceding *start* and that the number of *start* and *end*
notifications always matches after a sequence of voiced/unvoiced decisions.

Core acceptance criteria (DEV_TASKS.md – 34.2):
• Uses *hypothesis* for randomised input generation.
• Exercises a broad range of decision sequences and silence thresholds.
• Achieves deterministic results by appending extra silence at the tail so any
  final *end* event is guaranteed to flush.
"""

import inspect
import sys
from pathlib import Path
from types import ModuleType

import hypothesis.strategies as st
from hypothesis import given, settings
from hypothesis import HealthCheck

# ---------------------------------------------------------------------------
# Ensure repository root is on *sys.path* so local imports resolve irrespective
# of where `pytest` is invoked from.
# ---------------------------------------------------------------------------
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.audio_listener import VADAudioGate  # noqa: E402


class _SeqVad:  # pylint: disable=too-few-public-methods
    """Simple *webrtcvad* replacement returning a predefined decision list."""

    def __init__(self, decisions: list[bool]):
        # Copy to avoid mutation by caller
        self._decisions = decisions.copy()

    def is_speech(self, _frame: bytes, _sr: int) -> bool:  # noqa: D401 – stub signature
        return self._decisions.pop(0) if self._decisions else False


@given(
    decisions=st.lists(st.booleans(), min_size=1, max_size=40),
    silence_ms=st.sampled_from([30, 60, 90]),
)
@settings(max_examples=30, deadline=None, suppress_health_check=(HealthCheck.function_scoped_fixture,))
def test_vad_gate_start_end_pairing(monkeypatch, decisions: list[bool], silence_ms: int):
    """Property: the VAD gate must emit balanced start/end events."""

    # Patch *webrtcvad.Vad* with our deterministic stub
    stub = _SeqVad(decisions + [False] * 20)  # add trailing silence to flush buffer

    import InstanceScrubber.audio_listener as al  # local module alias for patching

    monkeypatch.setattr(al.webrtcvad, "Vad", lambda _lvl=2: stub)

    events: list[str] = []

    def _on_start():
        events.append("start")

    def _on_end(_buf: bytes):  # noqa: D401 – callback signature
        events.append("end")

    gate = VADAudioGate(
        frame_duration_ms=30,
        silence_threshold_ms=silence_ms,
        on_speech_start=_on_start,
        on_speech_end=_on_end,
    )

    # Dummy 30-ms PCM frame (16 kHz, 16-bit mono)
    frame = b"\x00\x00" * int(16_000 * (30 / 1000))

    for _ in range(len(decisions) + 20):
        gate.process_frame(frame)

    # Invariant 1 – same number of *start* and *end* events.
    assert events.count("start") == events.count("end")
    # Invariant 2 – events alternate correctly (no two consecutive identical values).
    for ev1, ev2 in zip(events, events[1:]):
        assert ev1 != ev2 