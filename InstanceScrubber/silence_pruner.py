from __future__ import annotations

"""Silence Pruner – trims long segments of near-zero audio.

This module fulfils *DEV_TASKS.md – Task 22* requirements:

22.1 Provide a helper that removes silence segments longer than a configurable
     threshold (default 2 minutes) **before** audio is forwarded to the heavy
     ASR model.  The goal is to avoid wasting GPU cycles on dead air when the
     user pauses a recording for a long time.

The implementation is pure-Python + NumPy only so that it remains lightweight
and testable in any CI environment (no external deps).
"""

from typing import List, Tuple

import numpy as np

__all__ = [
    "prune_long_silences",
    "prune_pcm_bytes",
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def prune_long_silences(
    audio: np.ndarray,
    *,
    sample_rate: int = 16_000,
    threshold_ms: int = 120_000,
    silence_level: int = 100,
) -> np.ndarray:
    """Return *audio* with long silence segments removed.

    Parameters
    ----------
    audio
        1-D ``np.int16`` PCM array.
    sample_rate
        Samples per second – **must** match the actual audio format.
    threshold_ms
        Minimum contiguous silence length (in milliseconds) that will be
        stripped.  The default value (120 000 ms) corresponds to *2 minutes*.
    silence_level
        A sample is considered *silent* when ``abs(sample) <= silence_level``.

    Notes
    -----
    • The algorithm uses a very cheap run-length scan so it can operate on long
      recordings without noticeable CPU overhead.
    • When *no* runs exceed *threshold_ms* the original array is returned
      *unmodified* to avoid an unnecessary copy.
    """

    if audio.size == 0:
        return audio  # Nothing to do.

    threshold_samples = int(sample_rate * threshold_ms / 1000)
    if threshold_samples <= 0:
        return audio

    # Fast boolean mask of *silent* samples.
    silence_mask = np.abs(audio) <= silence_level
    if not silence_mask.any():
        return audio  # early exit – no silence at all

    # Find run-lengths of consecutive *True* values in the mask.
    # Adapted from NumPy run-length-encoding idiom.
    diff = np.diff(silence_mask.astype(np.int8))
    run_starts = np.where(diff == 1)[0] + 1  # transition from 0→1 marks start
    run_ends = np.where(diff == -1)[0] + 1   # transition from 1→0 marks end

    # Handle edge cases where the array starts or ends with silence.
    if silence_mask[0]:
        run_starts = np.r_[0, run_starts]
    if silence_mask[-1]:
        run_ends = np.r_[run_ends, audio.size]

    # Build list of (start, end) pairs exceeding the threshold.
    remove_ranges: List[Tuple[int, int]] = []
    for start, end in zip(run_starts, run_ends):
        if end - start >= threshold_samples:
            remove_ranges.append((start, end))

    if not remove_ranges:
        return audio  # Nothing long enough to prune.

    # Stitch together the *keep* segments.
    keep_chunks: List[np.ndarray] = []
    last_idx = 0
    for start, end in remove_ranges:
        if last_idx < start:
            keep_chunks.append(audio[last_idx:start])
        last_idx = end
    if last_idx < audio.size:
        keep_chunks.append(audio[last_idx:])

    if not keep_chunks:
        # Corner-case: audio is *all* silence – return a zero-length array.
        return np.empty(0, dtype=np.int16)

    return np.concatenate(keep_chunks)


def prune_pcm_bytes(
    audio_bytes: bytes,
    *,
    sample_rate: int = 16_000,
    threshold_ms: int = 120_000,
    silence_level: int = 100,
) -> bytes:
    """Wrapper around :func:`prune_long_silences` operating on raw PCM bytes."""

    # Ensure even length so it can be viewed as int16 – otherwise bail out.
    if len(audio_bytes) % 2:
        return audio_bytes

    try:
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
    except ValueError:
        # Safety – if the buffer cannot be interpreted, return unmodified bytes.
        return audio_bytes

    pruned = prune_long_silences(
        audio_np,
        sample_rate=sample_rate,
        threshold_ms=threshold_ms,
        silence_level=silence_level,
    )
    return pruned.tobytes() 