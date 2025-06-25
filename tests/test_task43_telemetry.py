"""Tests for DEV_TASKS – Task 43 (Telemetry & Observability).

These tests cover both subtasks:

* **43.1** – Optional runtime metrics collection via OpenTelemetry with local
  JSON-Lines export.
* **43.2** – Ensuring *disabled* telemetry performs **no** outbound network
  calls (regression guard against inadvertent OTLP exporters).
"""

from __future__ import annotations

import socket
import time
from pathlib import Path

import pytest

from InstanceScrubber.config_manager import ConfigManager
from InstanceScrubber.telemetry_manager import TelemetryManager


@pytest.fixture()
def _temp_metrics_dir(tmp_path: Path):
    """Provide a dedicated directory for metric exports to keep the workspace clean."""
    yield tmp_path
    # Defensive – remove generated files so the *trash file* policy is honoured.
    for file in tmp_path.iterdir():
        try:
            file.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass


def test_metrics_export_when_enabled(_temp_metrics_dir: Path):
    """Enabling telemetry should create and write to a metrics file."""
    cfg = ConfigManager(app_name="TestTelemetry")
    cfg.set("telemetry_enabled", True)

    tm = TelemetryManager(cfg, metrics_dir=_temp_metrics_dir)
    tm.record_event("unit_test_event")

    # Force immediate export instead of waiting for background thread.
    tm.force_flush()
    time.sleep(0.1)  # Brief pause to allow file I/O to complete

    exported_files = list(_temp_metrics_dir.glob("*.jsonl"))
    assert exported_files, "No metrics files were written when telemetry is enabled."
    assert any(f.stat().st_size > 0 for f in exported_files), "Exported metrics file is empty."  # type: ignore[func-returns-value]

    # Clean-up so CI trash-file guard passes.
    tm.stop()


def test_no_network_calls_when_disabled(monkeypatch):
    """Disabling telemetry must not trigger any outgoing network traffic."""

    # Monkey-patch *socket.socket.connect* to raise if called – if the telemetry
    # manager unexpectedly attempts a network connection this will fail the test.
    def _deny_network_calls(self, *_a, **_kw):  # noqa: D401 – monkey-patch helper
        raise AssertionError("Disallowed outbound network call detected!")

    monkeypatch.setattr(socket.socket, "connect", _deny_network_calls, raising=True)

    cfg = ConfigManager(app_name="TestTelemetryDisabled")
    cfg.set("telemetry_enabled", False)

    tm = TelemetryManager(cfg)
    # Emit a dummy event – should *not* result in any network activity.
    tm.record_event("should_be_ignored")

    # If no assertion fired, behaviour is correct.
    tm.stop()