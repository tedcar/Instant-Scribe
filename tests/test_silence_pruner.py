from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest

# Ensure local imports work regardless of pytest invocation path
import sys
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.silence_pruner import prune_long_silences, prune_pcm_bytes  # noqa: E402


@pytest.fixture()
def _sample_audio():
    """Return tuple (*orig*, *silence_segment*) for reuse across tests."""
    sr = 16_000
    # 1 s voiced (value 1000) + 121 s silence + 1 s voiced
    voiced_1 = np.full(sr, 1000, dtype=np.int16)
    silence = np.zeros(sr * 121, dtype=np.int16)  # > 2 min
    voiced_2 = np.full(sr, 1000, dtype=np.int16)
    original = np.concatenate([voiced_1, silence, voiced_2])
    return original, silence


def test_pruner_removes_long_silence(_sample_audio):
    """Audio length should shrink by at least the 2-minute threshold."""
    original, silence = _sample_audio
    pruned = prune_long_silences(original, threshold_ms=120_000)

    sr = 16_000
    threshold_samples = sr * 120  # 2 minutes

    # Ensure we actually removed ≥ threshold_samples
    assert len(original) - len(pruned) >= threshold_samples

    # The pruned output should retain the non-silent sections (≈ 2 s)
    assert len(pruned) <= len(original) - threshold_samples
    # Ensure the resulting audio still contains the voiced parts (non-zero)
    assert np.any(np.abs(pruned) > 0)


def test_pruner_no_effect_when_below_threshold():
    """Silence shorter than threshold must remain unmodified."""
    sr = 16_000
    short_silence = np.zeros(sr * 30, dtype=np.int16)  # 30 s < threshold
    pruned = prune_long_silences(short_silence, threshold_ms=120_000)
    # Should be identical – no trimming when under threshold
    assert len(pruned) == len(short_silence)


def test_prune_pcm_bytes_roundtrip(_sample_audio):
    """Byte-level helper should transparently round-trip via int16 <-> bytes."""
    original, _ = _sample_audio
    bytes_in = original.tobytes()
    bytes_out = prune_pcm_bytes(bytes_in, threshold_ms=120_000)

    # Output is bytes and length is even (int16 alignment)
    assert isinstance(bytes_out, (bytes, bytearray))
    assert len(bytes_out) % 2 == 0

    # Decode to NumPy to verify the trimming logic is applied.
    result = np.frombuffer(bytes_out, dtype=np.int16)
    assert len(result) < len(original)  # trimmed down 