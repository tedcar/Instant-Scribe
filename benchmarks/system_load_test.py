"""End-to-End System Load Test (DEV_TASKS – Task 40).

This script simulates a long-running recording session and collects
CPU, RAM and *optional* GPU VRAM utilisation metrics.  It fails with a
non-zero exit-code when any of the following conditions are met:

* The free VRAM after the test differs by more than **5 %** compared to
  the initial value (indicates a memory leak).
* An un-handled exception occurs during sampling / orchestration.

The default runtime is **8 hours**.  For CI and unit-tests the duration
can be shortened dramatically via ``--duration-sec``.

A self-contained HTML report with Grafana-style graphs is written to the
output directory (default *reports/system_load/*).
"""
from __future__ import annotations

import argparse
import gc
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil  # lightweight, already pinned in requirements
import matplotlib.pyplot as plt

# Insert repository root on sys.path so 'instant_scribe' resolves when the
# script is executed directly from the *benchmarks/* subdirectory.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:  # noqa: WPS459 – intentional sys.path tweak
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Optional GPU helpers (pynvml may be unavailable on CI / CPU-only hosts)
# ---------------------------------------------------------------------------
try:
    import pynvml  # type: ignore

    pynvml.nvmlInit()  # Initialise once – fast when GPU missing
    _NVML_AVAILABLE = True
except Exception:  # noqa: BLE001 – import/runtime errors collapse to *unavailable*
    pynvml = None  # type: ignore
    _NVML_AVAILABLE = False


def _get_free_vram_mb() -> Optional[float]:  # noqa: D401 – helper
    """Return GPU *free* VRAM in **MiB** or *None* when unavailable."""
    if not _NVML_AVAILABLE:
        return None
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # type: ignore[attr-defined]
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)  # type: ignore[attr-defined]
        return mem.free / (1024 * 1024)
    except Exception:  # pragma: no cover – NVML runtime failure
        return None


# ---------------------------------------------------------------------------
# Core load-test logic
# ---------------------------------------------------------------------------

def run_load_test(
    *,
    duration_sec: float,
    interval_sec: float,
    output_dir: Path,
    use_stub: bool = False,
) -> None:  # noqa: D401 – imperative helper
    """Run the load-test and **raise** on failure (used by pytest).

    Parameters
    ----------
    duration_sec:
        How long the test should run (wall-clock seconds).
    interval_sec:
        Metric sampling interval in seconds.
    output_dir:
        Destination folder for metrics JSON, plot PNG and report HTML.
    use_stub:
        When *True* the orchestrator loads a *stub* transcription engine
        (no GPU RAM usage) for fast CI execution.
    """
    from instant_scribe.application_orchestrator import ApplicationOrchestrator

    output_dir.mkdir(parents=True, exist_ok=True)
    metrics: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Spin-up orchestrator (loads model & components)
    # ------------------------------------------------------------------
    orch = ApplicationOrchestrator(use_stub_worker=use_stub, auto_start=True)

    logging.info("Orchestrator started – beginning metric collection …")

    initial_free_vram = _get_free_vram_mb()
    start_ts = time.time()
    next_sample = start_ts
    end_ts = start_ts + duration_sec

    try:
        while time.time() < end_ts:
            now = time.time()
            if now >= next_sample:
                vm = psutil.virtual_memory()
                sample: Dict[str, Any] = {
                    "timestamp": now,
                    "cpu_percent": psutil.cpu_percent(interval=None),
                    "ram_used_mb": vm.used / (1024 * 1024),
                    "ram_percent": vm.percent,
                }
                free_vram = _get_free_vram_mb()
                if free_vram is not None:
                    sample["gpu_free_mb"] = free_vram
                metrics.append(sample)
                next_sample += interval_sec
            time.sleep(0.2)
    finally:
        # ------------------------------------------------------------------
        # Tear-down – attempt model unload & graceful shutdown
        # ------------------------------------------------------------------
        try:
            orch.auto_unload_model()
        except Exception:  # noqa: BLE001 – robustness during shutdown
            pass
        gc.collect()
        final_free_vram = _get_free_vram_mb()

        orch.shutdown()

    # ----------------------------------------------------------------------
    # Analyse VRAM drift – **must** be < 5 % (Task 40.2)
    # ----------------------------------------------------------------------
    drift_pct: Optional[float]
    if initial_free_vram is not None and final_free_vram is not None and initial_free_vram > 0:
        drift_pct = abs(final_free_vram - initial_free_vram) / initial_free_vram * 100.0
    else:
        drift_pct = None  # GPU unavailable – skip check

    if drift_pct is not None and drift_pct > 5.0:
        raise RuntimeError(
            f"VRAM free changed by {drift_pct:.2f}% (> 5%) – indicates leak")

    # ----------------------------------------------------------------------
    # Persist raw metrics JSON
    # ----------------------------------------------------------------------
    metrics_json = output_dir / "system_load_metrics.json"
    with metrics_json.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    # ----------------------------------------------------------------------
    # Create PNG time-series plot (CPU / RAM / GPU-free)
    # ----------------------------------------------------------------------
    if metrics:  # guard against empty list (extremely short run)
        _plot_metrics(metrics, output_dir / "system_load_plot.png")

    # ----------------------------------------------------------------------
    # Generate simple self-contained HTML report
    # ----------------------------------------------------------------------
    html_report = output_dir / "system_load_report.html"
    _write_html_report(html_report, metrics_json.name, drift_pct)

    logging.info("Load-test complete – report written to %s", html_report)


# ---------------------------------------------------------------------------
# Helper – Plotting
# ---------------------------------------------------------------------------

def _plot_metrics(metrics: List[Dict[str, Any]], png_path: Path) -> None:  # noqa: D401
    base_ts = metrics[0]["timestamp"]
    times = [(m["timestamp"] - base_ts) / 60 for m in metrics]  # minutes offset
    cpu = [m["cpu_percent"] for m in metrics]
    ram = [m["ram_percent"] for m in metrics]
    gpu_free = [m.get("gpu_free_mb") for m in metrics]

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax1.plot(times, cpu, label="CPU %", color="tab:red")
    ax1.plot(times, ram, label="RAM %", color="tab:blue")

    ax1.set_xlabel("Time (minutes)")
    ax1.set_ylabel("Utilisation (%)")
    ax1.legend(loc="upper left")

    if any(gpu_free):
        ax2 = ax1.twinx()
        ax2.plot(times, gpu_free, label="GPU free (MB)", color="tab:green")
        ax2.set_ylabel("Free VRAM (MB)")
        ax2.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Helper – HTML report writer
# ---------------------------------------------------------------------------

def _write_html_report(html_path: Path, json_name: str, drift_pct: Optional[float]) -> None:  # noqa: D401
    drift_str = (
        f"{drift_pct:.2f}% change in free VRAM" if drift_pct is not None else "GPU not detected"
    )
    html = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <title>Instant Scribe – System Load Test</title>
    <style>
        body {{ font-family: sans-serif; margin: 1rem 2rem; }}
        h1   {{ color: #2c3e50; }}
        .summary {{ margin-bottom: 1rem; }}
    </style>
</head>
<body>
    <h1>System Load Test Report</h1>
    <p class=\"summary\"><strong>VRAM Drift:</strong> {drift_str}</p>
    <img src=\"system_load_plot.png\" alt=\"Resource utilisation plot\"/>
    <p>Raw metrics available in <code>{json_name}</code>.</p>
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _parse_cli(argv: List[str]) -> argparse.Namespace:  # noqa: D401
    p = argparse.ArgumentParser(description="Instant Scribe – End-to-End System Load Test (Task 40)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--duration-hours", type=float, default=8.0, help="Run time in hours (default 8)")
    g.add_argument("--duration-sec", type=float, help="Run time in seconds (overrides --duration-hours)")
    p.add_argument("--interval-sec", type=float, default=60.0, help="Sampling interval in seconds (default 60)")
    p.add_argument("--output-dir", type=Path, default=Path("reports/system_load"), help="Directory for output artefacts")
    p.add_argument("--use-stub", action="store_true", help="Use stub transcription engine (no GPU usage)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:  # noqa: D401 – script entry
    args = _parse_cli(argv or sys.argv[1:])

    duration = args.duration_sec if args.duration_sec is not None else args.duration_hours * 3600

    try:
        run_load_test(
            duration_sec=duration,
            interval_sec=args.interval_sec,
            output_dir=args.output_dir,
            use_stub=args.use_stub,
        )
    except Exception as exc:  # noqa: BLE001 – propagate as exit-code 1
        logging.error("System load test failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main() 