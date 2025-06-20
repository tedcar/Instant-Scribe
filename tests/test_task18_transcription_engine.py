# Tests for *InstanceScrubber.transcription_worker.TranscriptionEngine* in
# *stub* mode to avoid heavyweight NVIDIA NeMo dependency.  These tests
# increase coverage for Task 18 while providing confidence that the public
# API behaves as documented when the real model is not available.

from __future__ import annotations

import numpy as np
import pytest

from InstanceScrubber.transcription_worker import TranscriptionEngine


def _make_silence(seconds: float = 1.0, sample_rate: int = 16_000) -> np.ndarray:
    """Utility: return a NumPy array of silent PCM samples."""
    length = int(seconds * sample_rate)
    return np.zeros(length, dtype=np.int16)


def test_plain_and_detailed_transcription_stub():
    """Engine should return deterministic strings in *stub* mode."""
    engine = TranscriptionEngine()
    engine.load_model(use_stub=True)

    audio = _make_silence(0.5)

    plain = engine.get_plain_transcription(audio)
    assert plain == "hello world"

    detailed_text, word_ts = engine.get_detailed_transcription(audio)
    assert detailed_text.startswith("hello world")
    assert isinstance(word_ts, list)

    # The benchmark should complete quickly and return a sensible RTF value.
    rtf = engine.benchmark_rtf(audio)
    assert rtf > 0

    # Unloading should clear the internal *model* reference.
    engine.unload_model()
    assert engine.model is None

    # After unloading, attempting transcription should raise RuntimeError.
    with pytest.raises(RuntimeError):
        engine.get_plain_transcription(audio)


def test_large_audio_handled_gracefully():
    """A ~30 min silent clip should not raise nor exhaust memory in stub mode."""
    engine = TranscriptionEngine()
    engine.load_model(use_stub=True)

    thirty_min_silence = _make_silence(30 * 60)
    text = engine.get_plain_transcription(thirty_min_silence)
    assert text == "hello world" 