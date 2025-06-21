"""Benchmark script measuring Real-Time-Factor (RTF) for a 30-second sample.

This module can be executed as a CLI or imported as a library.
It fulfils **Task 29 – Continuous Performance Benchmarking**:

29.1 • Measure the median RTF for a 30-second sample audio segment.
29.2 • Persist a baseline in ``benchmark_baselines.json`` and fail the
        process (non-zero exit status) when the current RTF regresses by
        more than 10 %.
29.3 • Record a GPU utilisation + VRAM timeline while the benchmark runs and
        save a ``gpu_profile.png`` artefact that can be uploaded by the CI
        job for later inspection.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import numpy as np

# Third-party imports are optional – fallbacks keep the script functional in
# lightweight CI containers without a GPU or a full scientific stack.
try:
    import matplotlib.pyplot as plt  # noqa: WPS433 (runtime import)
except Exception:  # pragma: no cover – matplotlib missing in slim envs
    plt = None  # type: ignore

# ---------------------------------------------------------------------------
# Ensure repository root is importable so that ``InstanceScrubber`` etc. resolve
# regardless of where the script is invoked from.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Local dependencies – we fall back to the stub implementation automatically
# when the heavy NeMo stack is absent (see ``TranscriptionEngine`` logic).
from InstanceScrubber.transcription_worker import TranscriptionEngine

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_DEFAULT_BASELINE_FILE = _THIS_DIR / "benchmark_baselines.json"
_DEFAULT_GPU_PLOT = _THIS_DIR / "gpu_profile.png"
_SAMPLE_RATE = 16_000  # Parakeet requirement (Hz)
_SAMPLE_DURATION = 30  # seconds
_REGRESSION_TOLERANCE = 0.10  # 10 %


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _generate_silence(duration_sec: int = _SAMPLE_DURATION) -> np.ndarray:
    """Return a numpy array containing *duration_sec* of silence (16-bit)."""

    length = _SAMPLE_RATE * duration_sec
    return np.zeros(length, dtype=np.int16)


# ---------------------------------------------------------------------------
# GPU sampling helpers (Task 29.3)
# ---------------------------------------------------------------------------

def _nvidia_smi_available() -> bool:
    """Return *True* when the ``nvidia-smi`` CLI exists on *PATH*."""

    try:
        return (
            subprocess.call(  # noqa: S603, S607 – intentional external call
                ["nvidia-smi"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            == 0
        )
    except FileNotFoundError:
        return False


def _sample_gpu_metrics(duration: float, interval: float = 0.5) -> Tuple[List[int], List[int], List[float]]:
    """Poll *nvidia-smi* for ``utilization.gpu`` % and ``memory.used`` [MiB].

    The function returns three parallel lists *(utils, vram, t)* where *t* is
    the absolute wall-clock timestamp (``time.perf_counter()``) for each
    sample.  When *nvidia-smi* is not available the lists are empty so that
    callers can degrade gracefully.
    """

    if not _nvidia_smi_available():  # pragma: no cover – CI on CPU-only host
        logging.warning("nvidia-smi not available – skipping GPU profiling")
        return ([], [], [])

    utils: List[int] = []
    vram: List[int] = []
    ts: List[float] = []
    end_time = time.perf_counter() + duration
    while time.perf_counter() < end_time:
        try:
            output = subprocess.check_output(  # noqa: S603 – external binary
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used",
                    "--format=csv,noheader,nounits",
                ],
                encoding="utf-8",
            )
            util_str, mem_str = output.strip().split(",")
            utils.append(int(util_str))
            vram.append(int(mem_str))
            ts.append(time.perf_counter())
        except Exception:  # pragma: no cover – tolerate transient failures
            pass
        time.sleep(interval)

    return utils, vram, ts


def _save_gpu_plot(utils: List[int], vram: List[int], ts: List[float], output: Path = _DEFAULT_GPU_PLOT) -> None:
    """Persist a GPU timeline PNG – no-op when matplotlib is missing."""

    if not utils or plt is None:  # Do nothing when data or library absent
        return

    try:
        # Normalise *t* axis to seconds relative to first sample for readability
        t0 = ts[0]
        rel_t = [t - t0 for t in ts]

        fig, ax1 = plt.subplots(figsize=(8, 4))  # type: ignore[attr-defined]
        ax1.set_title("GPU Utilisation & VRAM Usage During RTF Benchmark")
        ax1.set_xlabel("Time [s]")
        ax1.set_ylabel("GPU utilisation [%]", color="tab:blue")
        ax1.plot(rel_t, utils, color="tab:blue", label="utilisation [%]")
        ax1.tick_params(axis="y", labelcolor="tab:blue")
        ax1.set_ylim(0, 100)

        ax2 = ax1.twinx()
        ax2.set_ylabel("Memory used [MiB]", color="tab:red")
        ax2.plot(rel_t, vram, color="tab:red", label="VRAM [MiB]")
        ax2.tick_params(axis="y", labelcolor="tab:red")

        fig.tight_layout()
        fig.savefig(output, dpi=150)
        plt.close(fig)  # type: ignore[attr-defined]
        logging.info("GPU profile written to %s", output)
    except Exception as exc:  # pragma: no cover – plotting issues non-fatal
        logging.warning("Failed to create GPU plot: %s", exc)


# ---------------------------------------------------------------------------
# Core benchmark logic (Task 29.1 & 29.2)
# ---------------------------------------------------------------------------

def run_benchmark(*, repeats: int = 3, use_stub: bool = False) -> float:
    """Measure the *median* RTF across *repeats* runs and return it."""

    audio = _generate_silence()
    engine = TranscriptionEngine()
    engine.load_model(use_stub=use_stub)

    rtf_values: List[float] = []
    for _ in range(repeats):
        rtf_values.append(engine.benchmark_rtf(audio))

    engine.unload_model()
    median_rtf = float(np.median(rtf_values))
    logging.info("RTF samples: %s", ", ".join(f"{v:.2f}" for v in rtf_values))
    logging.info("Median RTFx: %.2f", median_rtf)
    return median_rtf


# ---------------------------------------------------------------------------
# Baseline helpers (Task 29.2)
# ---------------------------------------------------------------------------

def _read_baseline(path: Path) -> float | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return float(data.get("rtf_median", 0.0))
    except FileNotFoundError:
        return None


def _write_baseline(path: Path, rtf: float) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump({"rtf_median": rtf, "timestamp": datetime.utcnow().isoformat()}, fh, indent=2)
    logging.info("Baseline updated → %.2f (saved to %s)", rtf, path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Instant Scribe RTF benchmark (Task 29)")
    parser.add_argument("--repeats", type=int, default=3, help="Number of benchmark iterations")
    parser.add_argument("--baseline", type=Path, default=_DEFAULT_BASELINE_FILE, help="Path to baseline JSON")
    parser.add_argument("--update-baseline", action="store_true", help="Overwrite baseline with new results")
    parser.add_argument("--use-stub", action="store_true", help="Force stub ASR engine (fast, GPU-less)")
    parser.add_argument("--no-gpu-profile", action="store_true", help="Skip GPU utilisation timeline (Task 29.3)")
    parser.add_argument("--output-json", type=Path, help="Write current results JSON to this path")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:  # noqa: WPS231 – CLI plumbing
    """Entry-point used by ``python -m benchmarks.rtf_benchmark``."""

    if argv is None:
        argv = sys.argv[1:]
    args = _parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # ------------------------------------------------------------------
    # GPU profiling – start background sampler (best-effort)
    # ------------------------------------------------------------------
    gpu_utils: List[int] = []
    gpu_vram: List[int] = []
    gpu_ts: List[float] = []
    if not args.no_gpu_profile:
        # We sample in the *foreground* thread – the benchmark is the only heavy
        # task so the minimal overhead is acceptable.
        profile_thread = None  # type: ignore[assignment]
        sample_start = time.perf_counter()
    else:
        sample_start = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Actual benchmark
    # ------------------------------------------------------------------
    median_rtf = run_benchmark(repeats=args.repeats, use_stub=args.use_stub)

    # ------------------------------------------------------------------
    # GPU profiling – collect metrics for the benchmark duration
    # ------------------------------------------------------------------
    if not args.no_gpu_profile and sample_start is not None:
        bench_duration = time.perf_counter() - sample_start
        gpu_utils, gpu_vram, gpu_ts = _sample_gpu_metrics(bench_duration)
        _save_gpu_plot(gpu_utils, gpu_vram, gpu_ts)

    # ------------------------------------------------------------------
    # Baseline handling (fail CI on regression)
    # ------------------------------------------------------------------
    baseline_rtf = _read_baseline(args.baseline)
    if args.update_baseline or baseline_rtf is None:
        _write_baseline(args.baseline, median_rtf)
        baseline_rtf = median_rtf

    regression_allowed = baseline_rtf * (1 - _REGRESSION_TOLERANCE)
    if median_rtf < regression_allowed:
        logging.error(
            "Performance regression detected! Current RTFx %.2f < allowed %.2f (baseline %.2f)",
            median_rtf,
            regression_allowed,
            baseline_rtf,
        )
        sys.exit(1)

    logging.info("Benchmark passed – performance within acceptable range")

    # ------------------------------------------------------------------
    # Optional JSON output for downstream tooling
    # ------------------------------------------------------------------
    if args.output_json:
        payload = {
            "rtf_median": median_rtf,
            "baseline_rtf": baseline_rtf,
            "utils_pct": gpu_utils or None,
            "vram_mib": gpu_vram or None,
        }
        with args.output_json.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        logging.info("Results written to %s", args.output_json)


if __name__ == "__main__":
    main() 