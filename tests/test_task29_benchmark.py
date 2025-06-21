"""Tests covering Task 29 – Continuous Performance Benchmarking.

These checks validate **the whole feature** rather than the individual
sub-tasks:

1. The median RTF is computed and is > 1× real-time (stub engine).
2. The benchmark script exits with *success* (code 0) when performance is
   within the configured 10 % threshold compared to the saved baseline.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Repository path plumbing so local imports resolve in all execution contexts
# ---------------------------------------------------------------------------

ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
BENCH_SCRIPT = ROOT_DIR / "benchmarks" / "rtf_benchmark.py"
BASELINE_JSON = ROOT_DIR / "benchmarks" / "benchmark_baselines.json"

sys.path.insert(0, str(ROOT_DIR))  # Ensure in-repo imports override site-pkgs

from InstanceScrubber.transcription_worker import (
    TranscriptionEngine,  # noqa: E402
)


@pytest.fixture()
def sample_audio_np() -> np.ndarray:  # noqa: D103
    return np.zeros(16_000 * 30, dtype=np.int16)  # 30 s of silence @ 16 kHz


def test_median_rtf_calculation(sample_audio_np):
    """The in-process helper should yield an RTF > 1 in stub mode."""

    engine = TranscriptionEngine()
    engine.load_model(use_stub=True)
    rtf = engine.benchmark_rtf(sample_audio_np)
    engine.unload_model()

    assert rtf > 1.0, (
        f"Expected RTF > 1 (faster than real-time), got {rtf:.2f}"  # noqa: WPS221
    )


def test_cli_script_passes(tmp_path):
    """Running the CLI with --use-stub must exit with status 0 (no regression)."""

    output_json = tmp_path / "run.json"

    completed = subprocess.run(  # noqa: S603 – internal call to python
        [
            sys.executable,
            str(BENCH_SCRIPT),
            "--repeats",
            "1",
            "--use-stub",
            "--baseline",
            str(BASELINE_JSON),
            "--output-json",
            str(output_json),
        ],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )

    # Debug aid on CI failures
    if completed.returncode != 0:
        pytest.fail(
            (
                f"Benchmark CLI failed (code {completed.returncode}):\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        )

    assert output_json.is_file(), "Benchmark did not write results JSON" 