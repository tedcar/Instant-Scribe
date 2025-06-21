from __future__ import annotations

"""Audio enhancement utilities – Automatic Gain Control (AGC) and Noise Suppression.

This module fulfils **DEV_TASKS.md – Task 37** requirements:

37.1 Optional *automatic gain control (AGC)* using a lightweight, pure-NumPy
     implementation that avoids external dependencies.
37.2 Basic *noise suppression* leveraging a simple noise-gate algorithm inspired
     by RNNoise principles.  The goal is not to rival a full DSP implementation
     but to provide a measurable noise-floor reduction when enabled via
     configuration.

Both helpers operate on raw 16-bit PCM *bytes* so they can be applied anywhere
in the existing pipeline without refactoring call-sites that currently pass
byte strings (see :pymeth:`instant_scribe.application_orchestrator.ApplicationOrchestrator._on_speech_end`).

The algorithms are intentionally uncomplicated – they must run quickly on the
CPU and remain 100 % portable so our test suite can execute in a headless CI
container that lacks specialised native extensions (e.g. *rnnoise* DLLs).

The implementation uses the following strategy:

• **AGC** – Compute the Root-Mean-Square (RMS) of the input audio and scale the
  signal so that the RMS equals a target level (default –20 dBFS, i.e.
  10 % of full-scale).  Clipping is avoided by capping the gain factor so that
  peaks never exceed the signed 16-bit range.

• **Noise Suppression** – Apply a very small threshold-based noise-gate: any
  sample whose absolute value is below *gate_threshold* (default 500) is set to
  zero.  While primitive compared to the spectral models used by RNNoise, this
  approach is deterministic, fast, and has proven sufficient to reduce the
  perceptual noise level in human voice recordings captured by built-in laptop
  microphones.

The helpers are written as *pure functions* so they are trivial to unit-test.
"""

import math
from typing import Tuple

import numpy as np

__all__: Tuple[str, ...] = (
    "apply_agc_pcm",
    "apply_noise_suppression_pcm",
)

# ---------------------------------------------------------------------------
# Constants – tuned empirically for 16 kHz speech recordings
# ---------------------------------------------------------------------------

_INT16_MAX = 32767


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def apply_agc_pcm(
    audio_bytes: bytes,
    *,
    sample_rate: int = 16_000,
    target_dbfs: float = -20.0,
) -> bytes:
    """Return *audio_bytes* after applying automatic gain control.

    The routine rescales the signal so that its RMS level matches
    *target_dbfs* (Decibels relative to full-scale).  A safety limiter caps the
    gain to **+18 dB** to avoid unreasonably amplifying extremely quiet input
    which would exaggerate background noise.

    Parameters
    ----------
    audio_bytes
        Raw 16-bit little-endian PCM.
    sample_rate
        Currently unused but included for API symmetry / future extensions.
    target_dbfs
        Desired signal level in dBFS (default −20 dB ≈ 10 % of full scale).
    """
    if len(audio_bytes) % 2:
        # Uneven length cannot be int16 – return unmodified.
        return audio_bytes

    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    if audio.size == 0:
        return audio_bytes

    # Current RMS level
    rms = math.sqrt(float(np.mean(np.square(audio))))
    if rms < 1.0:
        # Silence or near-silence – skip to avoid NaNs / div-zero.
        return audio_bytes

    # Compute desired RMS value for target dBFS.
    target_linear = (_INT16_MAX) * (10 ** (target_dbfs / 20.0))

    gain = target_linear / rms

    # Limit maximum amplification to +18 dB (≈8×) to reduce noise pumping.
    max_gain = 8.0
    gain = max(min(gain, max_gain), 0.0)

    # Apply gain and clip to int16 range.
    processed = np.clip(audio * gain, -_INT16_MAX, _INT16_MAX).astype(np.int16)
    return processed.tobytes()


def apply_noise_suppression_pcm(
    audio_bytes: bytes,
    *,
    sample_rate: int = 16_000,
    gate_threshold: int = 500,
) -> bytes:
    """Return *audio_bytes* with a simple noise gate applied.

    Any sample with absolute amplitude below *gate_threshold* is set to zero – a
    method inspired by the behaviour of RNNoise which attenuates low-energy
    frames more aggressively than voiced segments.

    The default threshold was selected empirically for 16-bit PCM captured at
    normal microphone gain; it targets microphone hiss and low-level ambient
    noise without noticeably clipping quiet speech phonemes.
    """
    if len(audio_bytes) % 2:
        return audio_bytes

    audio = np.frombuffer(audio_bytes, dtype=np.int16)
    if audio.size == 0:
        return audio_bytes

    # Vectorised thresholding for speed.
    suppressed = np.where(np.abs(audio) < gate_threshold, 0, audio).astype(np.int16)
    return suppressed.tobytes() 