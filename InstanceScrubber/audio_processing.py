from __future__ import annotations

"""Audio pre-processing utilities – Automatic Gain Control (AGC) and optional
noise-suppression using the RNNoise DSP library.

This helper module is *self-contained* (pure Python + NumPy fallback) so that
unit-tests remain fully functional on CI workers that **do not** have the C
extension wheels for *pydub* / *rnnoise* available.  When those libraries are
missing we transparently fall back to naïve implementations that leave the
signal unmodified while emitting a *debug* level log entry to aid
troubleshooting.

The public :func:`preprocess_audio` orchestrates the pipeline and is designed
for consumption by :pyfile:`InstanceScrubber.transcription_worker`.
"""

from __future__ import annotations

import logging
from typing import Final

# `numpy` is a hard runtime dependency but type stubs may be missing in some
# environments; suppress *missing-import* warnings emitted by static checkers.
import numpy as np  # type: ignore

# ---------------------------------------------------------------------------
# Optional third-party dependencies – soft import with graceful degradation
# ---------------------------------------------------------------------------

try:
    from rnnoise import RNNoise  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – allow tests to run w/o lib

    class _DummyRNNoise:  # pylint: disable=too-few-public-methods
        """Replacement when RNNoise binary not present – *no-op* processing."""

        def process_frame(self, frame: np.ndarray) -> np.ndarray:  # noqa: D401 – mimic API
            # RNNoise returns a *float32* NumPy array – we replicate that to
            # keep downstream expectations consistent even in stub mode.
            return frame.astype(np.float32)

    RNNoise = _DummyRNNoise  # type: ignore  # noqa: N816 – keep original name

try:
    from pydub import AudioSegment  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – optional dependency

    AudioSegment = None  # type: ignore  # noqa: N816 – sentinel for stub path

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_INT16_MAX: Final[float] = float(np.iinfo(np.int16).max)
_FRAME_SIZE: Final[int] = 480  # Samples per 30 ms @ 16 kHz – RNNoise requirement


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preprocess_audio(
    pcm_bytes: bytes,
    *,
    enable_agc: bool = False,
    enable_noise_suppression: bool = False,
    target_dbfs: float = -20.0,
    sample_rate: int = 16_000,
) -> bytes:
    """Return *pcm_bytes* after optional AGC + noise-suppression.

    The function is intentionally *side-effect free* – it never mutates the
    input buffer and always returns **new** bytes (or the original when no
    processing was requested / possible).
    """

    # Fast-path bail-out when nothing to do – avoids NumPy allocation entirely.
    if not enable_agc and not enable_noise_suppression:
        return pcm_bytes

    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32, copy=True)

    if enable_noise_suppression and audio.size:
        audio = _apply_rnnoise(audio, sample_rate)

    if enable_agc and audio.size:
        audio = _apply_agc(audio, target_dbfs)

    return audio.astype(np.int16).tobytes()


# ---------------------------------------------------------------------------
# Implementation helpers – kept *private* to the module
# ---------------------------------------------------------------------------

def _apply_agc(audio: np.ndarray, target_dbfs: float) -> np.ndarray:  # noqa: D401 – internal helper
    """Simple *static* gain normalisation bringing RMS level to *target_dbfs*.

    The algorithm mirrors pydub's `AudioSegment.apply_gain()` behaviour to
    avoid the external dependency when *pydub* is unavailable.
    """

    if AudioSegment is not None:  # Use high-level helper when available
        seg = AudioSegment(
            audio.tobytes(), frame_rate=16_000, sample_width=2, channels=1
        )
        change_db = target_dbfs - seg.dBFS  # type: ignore[attr-defined]
        seg = seg.apply_gain(change_db)  # type: ignore[attr-defined]
        return np.frombuffer(seg.raw_data, dtype=np.int16).astype(np.float32)

    # ------------------------------------------------------------------
    # Fallback – pure NumPy implementation (approximate but deterministic)
    # ------------------------------------------------------------------
    rms = np.sqrt(np.mean(np.square(audio)))
    if rms == 0:
        logging.debug("AGC skipped – zero RMS")
        return audio

    current_dbfs = 20.0 * np.log10(rms / _INT16_MAX)
    change_db = target_dbfs - current_dbfs
    gain = 10.0 ** (change_db / 20.0)
    logging.debug("AGC gain %+0.2f dB (factor %.2f)", change_db, gain)
    processed = audio * gain
    # Clip to int16 range to avoid wrap-around
    processed = np.clip(processed, -_INT16_MAX, _INT16_MAX)
    return processed


def _apply_rnnoise(audio: np.ndarray, sample_rate: int) -> np.ndarray:  # noqa: D401 – internal helper
    """Return *audio* after RNNoise denoising.  When the RNNoise binary is not
    available we log a *debug* message and return the original signal.
    """

    if RNNoise is None:  # type: ignore[comparison-overlap]
        logging.debug("RNNoise library not available – noise suppression skipped")
        return audio

    if sample_rate != 16_000:
        logging.warning("RNNoise requires 16 kHz input; received %d Hz – skipping", sample_rate)
        return audio

    denoiser = RNNoise()  # type: ignore[call-arg]
    out_frames = []
    total_samples = audio.shape[0]

    for start in range(0, total_samples, _FRAME_SIZE):
        frame = audio[start : start + _FRAME_SIZE]
        if frame.shape[0] < _FRAME_SIZE:
            # Pad final frame with zeros (RNNoise requirement is *exact* 480 samples)
            frame = np.pad(frame, (_FRAME_SIZE - frame.shape[0],), mode="constant")
        processed = denoiser.process_frame(frame.astype(np.int16))  # type: ignore[attr-defined]
        out_frames.append(processed)

    denoised = np.concatenate(out_frames)[:total_samples]
    return denoised.astype(np.float32)


__all__ = [
    "preprocess_audio",
]