from __future__ import annotations

"""Telemetry & Observability utilities (DEV_TASKS – Task 43).

This lightweight helper conditionally initialises an OpenTelemetry *MeterProvider*
that exports runtime metrics to a local file inside the *metrics/* directory.
Collection is **disabled by default** and controlled via the
``telemetry_enabled`` configuration key that lives in
:pyattr:`InstanceScrubber.config_manager.ConfigManager.DEFAULTS`.

The implementation purposefully keeps its external dependencies optional – if
*opentelemetry-sdk* is missing at runtime the manager logs a warning and
silently disables itself so the main application continues to function.
"""

from pathlib import Path
import json
import logging
import time
from typing import Any, Dict, Optional

# Avoid importing OpenTelemetry on module import to keep startup fast.

logger = logging.getLogger(__name__)


class TelemetryManager:  # pylint: disable=too-few-public-methods
    """Thin wrapper around *OpenTelemetry* metric API.

    Parameters
    ----------
    config:
        An already initialised :class:`~InstanceScrubber.config_manager.ConfigManager`
        instance so we can read user preferences.
    metrics_dir:
        Optional override for the folder where metric files are written.  Used
        mainly by the test-suite to point exports at a temporary directory.
    """

    def __init__(self, config: Any, *, metrics_dir: Optional[Path] = None) -> None:  # noqa: ANN401 – config is duck-typed
        self._enabled: bool = bool(config.get("telemetry_enabled", False))
        self._meter = None
        self._shutdown_cb = None  # type: ignore[assignment]

        if not self._enabled:
            logger.debug("Telemetry disabled via config – skipping initialisation")
            return

        try:
            # Local import so missing dependency triggers ImportError only when
            # telemetry is *actually* enabled.
            from opentelemetry import metrics  # type: ignore
            from opentelemetry.sdk.metrics import MeterProvider  # type: ignore
            from opentelemetry.sdk.resources import Resource  # type: ignore
            from opentelemetry.sdk.metrics.export import (  # type: ignore
                MetricExporter,
                MetricExportResult,
                PeriodicExportingMetricReader,
            )
        except ImportError as exc:  # pragma: no cover – optional dep
            logger.warning("OpenTelemetry not available – telemetry disabled (%s)", exc)
            self._enabled = False
            return

        # ------------------------------------------------------------------
        # Simple JSON-Lines exporter writing one OTel *MetricsData* protobuf per
        # line.  This is intentionally naïve – it fulfils the requirement of
        # **local** metric persistence without sending any data over the
        # network.
        # ------------------------------------------------------------------
        class _FileMetricExporter(MetricExporter):
            def __init__(self, file_path: Path):  # noqa: D401 – internal helper
                super().__init__(preferred_temporality={})
                self._path = file_path
                self._path.parent.mkdir(parents=True, exist_ok=True)

            # noqa: D401 – signature mandated by ABC
            def export(self, metrics_data) -> "MetricExportResult":  # type: ignore[override]
                try:
                    serialised = str(metrics_data)  # String-ify protobuf for now.
                    with self._path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"raw": serialised}) + "\n")
                except Exception as exc:  # pylint: disable=broad-except
                    logger.debug("Failed to write metrics batch: %s", exc)
                    return MetricExportResult.FAILURE
                return MetricExportResult.SUCCESS

            def shutdown(self):  # noqa: D401 – override
                return MetricExportResult.SUCCESS

            # Newer OpenTelemetry SDKs mandate *force_flush* in the exporter
            # interface – provide a trivial implementation so the stub
            # satisfies the ABC.
            def force_flush(self, timeout_millis: int = 10_000):  # noqa: D401, ANN001
                return True

        # Default export location ------------------------------------------------
        if metrics_dir is None:
            metrics_dir = Path.cwd() / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        file_path = metrics_dir / f"metrics_{int(time.time())}.jsonl"

        exporter = _FileMetricExporter(file_path)
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5000)

        provider = MeterProvider(
            metric_readers=[reader],
            resource=Resource.create({"service.name": "instant_scribe"}),
        )
        metrics.set_meter_provider(provider)

        # Store shutdown callback so callers can flush & close on exit.
        self._shutdown_cb = provider.shutdown  # type: ignore[assignment]
        self._meter = metrics.get_meter(__name__)
        self._counter = self._meter.create_counter("recorded_events")

        logger.debug("Telemetry initialised – writing to %s", file_path)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def record_event(self, name: str, value: int = 1, attrs: Optional[Dict[str, Any]] = None) -> None:  # noqa: D401
        """Increment a generic *event* counter.

        The helper is intentionally generic – higher-level components can pass
        ``attrs`` to differentiate between event types (e.g. ``{"type":
        "transcription"}``).
        """
        if not self._enabled or self._meter is None:
            return

        try:
            self._counter.add(value, attributes=attrs or {"event": name})  # type: ignore[arg-type]
        except Exception as exc:  # pylint: disable=broad-except
            # Telemetry must never crash the application
            logger.debug("Telemetry record_event failed: %s", exc)

    # ..................................................................
    def stop(self) -> None:  # noqa: D401 – imperative API
        """Flush remaining metrics and shutdown exporter."""
        if not self._enabled or self._shutdown_cb is None:
            return
        try:
            self._shutdown_cb()
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("Telemetry shutdown failed: %s", exc)