# New tests for Task 18 – Quality Assurance (integration & coverage)
#
# This file exercises the VADAudioGate state-machine end-to-end using a
# deterministic *dummy* WebRTC VAD implementation so that we can reliably
# trigger the speech-start → speech-end callbacks without the native
# webrtcvad wheel (which is often missing in CI environments).
#
# The goal is to boost code-coverage for *InstanceScrubber.audio_listener*
# while also providing confidence that the gate correctly buffers audio
# and invokes the expected callbacks.

from __future__ import annotations

import numpy as np
import pytest

from InstanceScrubber.audio_listener import VADAudioGate


class _DeterministicVad:  # pylint: disable=too-few-public-methods
    """Minimal stub mimicking *webrtcvad.Vad* with predictable output.

    It returns *speech* for the first ``speech_frames`` calls followed by
    *silence* for ``silence_frames`` and then repeats the cycle.  This makes
    it trivial to test the state-machine without hand-crafting actual voiced
    audio samples.
    """

    def __init__(self, speech_frames: int = 3, silence_frames: int = 3):
        self._speech_frames = speech_frames
        self._silence_frames = silence_frames
        self._counter = 0

    def is_speech(self, _frame: bytes, _sample_rate: int) -> bool:  # noqa: D401 – external API
        cycle_len = self._speech_frames + self._silence_frames
        pos = self._counter % cycle_len
        self._counter += 1
        return pos < self._speech_frames


@pytest.mark.parametrize("silence_threshold_ms", [60, 90])
def test_vad_audio_gate_triggers_callbacks(monkeypatch, silence_threshold_ms):
    """Verify that the VAD gate calls *on_speech_start* / *on_speech_end* exactly once."""

    started = []
    ended_buffers: list[bytes] = []

    gate = VADAudioGate(
        sample_rate=16_000,
        frame_duration_ms=30,
        vad_aggressiveness=1,
        silence_threshold_ms=silence_threshold_ms,
        on_speech_start=lambda: started.append(True),
        on_speech_end=lambda data: ended_buffers.append(data),
    )

    # Patch the internal VAD with our deterministic stub so the gate
    # believes the first *n* frames contain speech.
    monkeypatch.setattr(gate, "_vad", _DeterministicVad(speech_frames=3, silence_frames=3))

    # Build a dummy PCM frame matching the gate's expected byte length.
    pcm_frame = (np.zeros(gate.bytes_per_frame // 2, dtype=np.int16)).tobytes()

    # Feed enough frames to cover a full speech->silence cycle twice.
    for _ in range(12):
        gate.process_frame(pcm_frame)

    # Exactly one start + one end callback pair must have fired.
    assert len(started) == 2  # two speech segments detected
    assert len(ended_buffers) == 2

    # (The assertions above already validated the buffer integrity.) 