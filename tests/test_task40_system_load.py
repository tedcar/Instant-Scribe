"""Tests covering Task 40 – End-to-End System Load Testing.

The *full* feature is validated rather than the individual sub-tasks:

1. The CLI script exits **successfully** (exit-code 0) when run with a
   short 3-second duration and stub ASR engine.
2. The script writes the expected *HTML report* and *metrics JSON* files.
"""
from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path plumbing so repo imports resolve regardless of invocation context
# ---------------------------------------------------------------------------
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
SCRIPT = ROOT_DIR / "benchmarks" / "system_load_test.py"


@pytest.mark.timeout(30)
def test_system_load_cli_smoke(tmp_path):  # noqa: D103 – pytest hook
    output_dir = tmp_path / "out"

    completed = subprocess.run(  # noqa: S603 – internal python call
        [
            sys.executable,
            str(SCRIPT),
            "--duration-sec",
            "3",  # 3 s keeps CI runtime low while exercising code-paths
            "--interval-sec",
            "1",
            "--use-stub",
            "--output-dir",
            str(output_dir),
        ],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        pytest.fail(
            (
                f"System load CLI failed (code {completed.returncode}):\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        )

    # Check artefacts exist ------------------------------------------------
    metrics_json = output_dir / "system_load_metrics.json"
    html_report = output_dir / "system_load_report.html"

    assert metrics_json.is_file(), "Metrics JSON not written"
    assert html_report.is_file(), "HTML report not written" 