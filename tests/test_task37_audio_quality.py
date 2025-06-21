import math

import numpy as np
import pytest

from InstanceScrubber.audio_enhancement import (
    apply_agc_pcm,
    apply_noise_suppression_pcm,
)


@pytest.fixture()
def _sine_wave_bytes():
    """Return 1-second 440 Hz sine wave (16-bit, 16 kHz) as raw PCM bytes."""
    sample_rate = 16_000
    duration_sec = 1.0
    t = np.arange(int(sample_rate * duration_sec)) / sample_rate
    # Quiet signal – intentionally low amplitude so AGC has visible effect
    waveform = (1000 * np.sin(2 * math.pi * 440.0 * t)).astype(np.int16)
    return waveform.tobytes()


def test_agc_increases_rms(_sine_wave_bytes):
    """AGC should raise the RMS level of a quiet recording."""
    original = np.frombuffer(_sine_wave_bytes, dtype=np.int16).astype(np.float32)
    processed = np.frombuffer(apply_agc_pcm(_sine_wave_bytes), dtype=np.int16).astype(
        np.float32
    )

    orig_rms = math.sqrt(float(np.mean(np.square(original))))
    proc_rms = math.sqrt(float(np.mean(np.square(processed))))

    # Expect at least 2× increase (≈ +6 dB).  The exact factor depends on
    # target_dbfs but +6 dB provides generous slack for test environments.
    assert proc_rms >= orig_rms * 2.0


def test_noise_gate_reduces_low_amplitude_regions(_sine_wave_bytes):
    """Noise suppression should zero-out a significant portion of background noise."""
    # Inject low-level Gaussian noise (µ=0, σ=300).  This is below the default
    # gate_threshold (500) so the noise-gate should remove most of it.
    noisy = (
        np.frombuffer(_sine_wave_bytes, dtype=np.int16).astype(np.int32)
        + np.random.normal(0, 300, size=16_000).astype(np.int32)
    ).astype(np.int16)

    noisy_bytes = noisy.tobytes()
    suppressed_bytes = apply_noise_suppression_pcm(noisy_bytes)

    # Count samples whose amplitude is < 500 before / after processing.
    noisy_arr = np.frombuffer(noisy_bytes, dtype=np.int16)
    suppressed_arr = np.frombuffer(suppressed_bytes, dtype=np.int16)

    # The noise gate should increase the number of *zero* samples substantially.
    zeros_before = int(np.sum(noisy_arr == 0))
    zeros_after = int(np.sum(suppressed_arr == 0))

    assert zeros_after > zeros_before * 5  # at least 5× more zeros 

def test_enhancement_edge_cases():
    """Edge cases: empty input and uneven length should return unchanged bytes."""
    empty = b""
    assert apply_agc_pcm(empty) == empty
    assert apply_noise_suppression_pcm(empty) == empty

    # Uneven length buffer (odd number of bytes)
    odd = b"\x00"
    assert apply_agc_pcm(odd) == odd
    assert apply_noise_suppression_pcm(odd) == odd 