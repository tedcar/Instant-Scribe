"""Tests covering **Task 31 – Privacy Audit & Network Guard**.

These checks validate the *entire* Task:

1. Static code scan (`scripts/privacy_audit.py`) detects **no** forbidden
   outbound-network imports in the application code (excluding tests).
2. A representative transcription cycle executes **without** performing any
   outbound socket connections (guarded via monkey-patch).
"""

from __future__ import annotations

import inspect
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
AUDIT_SCRIPT = ROOT_DIR / "scripts" / "privacy_audit.py"

# ---------------------------------------------------------------------------
# 31.1 – Static import scan must pass (exit status 0)
# ---------------------------------------------------------------------------

def test_privacy_audit_cli_passes():
    """Running the privacy-audit CLI must succeed (no forbidden imports)."""

    completed = subprocess.run(  # noqa: S603 – internal call to python
        [sys.executable, str(AUDIT_SCRIPT), "--fail-on-detected"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        pytest.fail(
            (
                f"Privacy audit failed (code {completed.returncode}):\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        )


# ---------------------------------------------------------------------------
# 31.2 – Runtime network-guard during a full transcription cycle
# ---------------------------------------------------------------------------

from InstanceScrubber.transcription_worker import (  # noqa: E402 – local import
    TranscriptionEngine,
)


@pytest.fixture()
def sample_audio_np() -> np.ndarray:  # noqa: D103
    return np.zeros(16_000, dtype=np.int16)  # 1 s of silence @ 16 kHz


def test_transcription_cycle_no_network(monkeypatch, sample_audio_np):
    """Ensure no outbound socket.connect occurs during transcription cycle."""

    attempted_connections: list[tuple] = []

    # Patch *socket.socket.connect* so any real outbound attempt fails the test.
    original_connect = socket.socket.connect

    def _spy_connect(self, address):  # noqa: D401 – spy wrapper
        attempted_connections.append(address)
        raise AssertionError(f"Outbound network attempt detected: {address}")

    monkeypatch.setattr(socket.socket, "connect", _spy_connect, raising=True)

    # Run a minimal transcription flow using the *stub* engine (no heavy deps).
    engine = TranscriptionEngine()
    engine.load_model(use_stub=True)
    _ = engine.get_plain_transcription(sample_audio_np)
    engine.unload_model()

    # Restore original connect (good practice, though monkeypatch will undo)
    monkeypatch.setattr(socket.socket, "connect", original_connect, raising=True)

    assert not attempted_connections, (
        "Expected zero outbound socket connections, "
        f"but observed: {attempted_connections}"
    ) 