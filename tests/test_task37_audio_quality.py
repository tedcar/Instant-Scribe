from __future__ import annotations

"""Tests covering Task 37 – Audio Quality Optimisations.

These focus on **the whole feature** rather than the minute implementation
--details:

1. Pre-processing pipeline (AGC + noise-suppression) must preserve PCM length
   and, when AGC is enabled, bring the RMS level closer to the target −20 dBFS.
2. The public *audio_quality_benchmark.py* CLI must execute successfully in
   *stub* mode so that CI can run it without the heavyweight GPU model.
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import math
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Third-party imports – add *type: ignore* to silence missing-stub warnings.
# ---------------------------------------------------------------------------

import numpy as np  # type: ignore
import pytest  # type: ignore

# ---------------------------------------------------------------------------
# Repository path plumbing – use __file__ to avoid FrameType typing issues
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[1]
BENCH_SCRIPT = ROOT_DIR / "benchmarks" / "audio_quality_benchmark.py"

sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.audio_processing import preprocess_audio  # noqa: E402


@pytest.fixture()
def sample_sine_pcm() -> bytes:  # noqa: D103 – PyTest fixture
    sr = 16_000
    t = np.arange(sr, dtype=np.float32) / sr  # 1-second buffer
    sine = 0.05 * np.sin(2 * math.pi * 440 * t)  # 5 % FS @ 440 Hz
    pcm = (sine * 32767).astype(np.int16)
    return pcm.tobytes()


def _rms_dbfs(pcm: bytes) -> float:  # noqa: D401 – helper
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if audio.size == 0:
        return -math.inf
    rms = math.sqrt(np.mean(np.square(audio)))
    if rms == 0:
        return -math.inf
    return 20 * math.log10(rms / 32767)


def test_agc_moves_towards_target(sample_sine_pcm):
    """AGC should shift RMS level closer to −20 dBFS (within 1 dB tolerance)."""

    original_db = _rms_dbfs(sample_sine_pcm)
    processed = preprocess_audio(sample_sine_pcm, enable_agc=True)
    processed_db = _rms_dbfs(processed)

    # The processed signal must be closer to the target than the original.
    assert abs(processed_db - (-20.0)) < abs(original_db - (-20.0))
    # And stay within a tight tolerance.
    assert math.isfinite(processed_db)
    assert -21.0 <= processed_db <= -19.0
    # PCM length must be preserved.
    assert len(processed) == len(sample_sine_pcm)


def test_cli_script_executes(tmp_path):
    """CLI benchmark should exit with code 0 in stub mode."""

    output_json = tmp_path / "res.json"

    completed = subprocess.run(  # noqa: S603 – internal test helper
        [sys.executable, str(BENCH_SCRIPT), "--use-stub", "--output-json", str(output_json)],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        pytest.fail(
            (
                f"Audio quality benchmark failed (code {completed.returncode}):\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        )

    assert output_json.is_file(), "Benchmark did not produce output JSON"