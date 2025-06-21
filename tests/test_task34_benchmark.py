from __future__ import annotations

"""Task 34 – Performance benchmark leveraging *pytest-benchmark*.

This micro-benchmark measures the throughput of
:pyfunc:`InstanceScrubber.audio_listener.VADAudioGate.process_frame` to detect
unexpected slow-downs (DEV_TASKS.md – 34.3).

It does **not** assert an absolute timing threshold (which would be brittle
across machines/CI runners).  Instead the collected results are stored in the
benchmark history so *pytest-benchmark* can compare future runs and fail on
regressions when invoked with ``--benchmark-sort=name --benchmark-compare`` in
CI (see docs).
"""

import inspect
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.audio_listener import VADAudioGate  # noqa: E402


def test_vad_gate_process_speed(benchmark):  # noqa: D401 – benchmark signature
    """Benchmark processing 1 000 silent frames through the VAD gate."""

    gate = VADAudioGate(silence_threshold_ms=60)

    # Pre-compute dummy PCM frame (30-ms 16-kHz mono silence)
    frame = b"\x00\x00" * int(16_000 * (30 / 1000))

    def _run():
        for _ in range(1_000):
            gate.process_frame(frame)

    benchmark(_run) 