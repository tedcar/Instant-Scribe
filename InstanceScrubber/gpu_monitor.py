from __future__ import annotations

"""GPU VRAM monitoring helper (Task 33 – GPU Resource Management).

This lightweight wrapper periodically samples NVIDIA GPU memory via
``pynvml`` and automatically triggers *model unload* when available
VRAM drops below a user-configurable threshold (default **1 GB**).

The class is intentionally **dependency-free** when *pynvml* is not
installed or a discrete NVIDIA GPU is missing.  In such environments
all public methods degrade to *no-op* so importing this module never
breaks unit-tests running on CPU-only CI runners.
"""

from typing import Optional, Any
import logging
import threading

try:
    import pynvml  # type: ignore

    _NVML_AVAILABLE = True
except ImportError:  # pragma: no cover – headless CI path
    pynvml = None  # type: ignore
    _NVML_AVAILABLE = False

__all__ = ["GPUResourceMonitor"]


class GPUResourceMonitor:
    """Background thread that watches free VRAM and **auto-unloads** the ASR model.

    The monitor is constructed and owned by :class:`~instant_scribe.application_orchestrator.ApplicationOrchestrator`.
    It calls back into the orchestrator via :pyfunc:`ApplicationOrchestrator.auto_unload_model` whenever the
    threshold condition is met.
    """

    def __init__(self, orchestrator: Any, config_manager: Any, notification_manager: Any):
        self._orch = orchestrator
        self._cfg = config_manager
        self._notify = notification_manager
        self._log = logging.getLogger(self.__class__.__name__)

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Lazily initialised NVML handle – *None* when unavailable.
        self._handle = None
        self._init_nvml()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def start(self) -> None:  # noqa: D401 – imperative API
        """Spin up the monitoring loop in a **daemon thread** (idempotent)."""
        if self._handle is None:
            return  # Monitoring disabled – silently ignore
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:  # noqa: D401 – imperative API
        """Signal the background loop to terminate and **join** the thread."""
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def check_once(self) -> None:  # noqa: D401 – imperative API
        """Expose a *single-shot* check for **unit-tests** to trigger manually."""
        self._check_once()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _init_nvml(self) -> None:
        if not _NVML_AVAILABLE:
            self._log.info("pynvml not available – GPU monitoring disabled")
            return
        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as exc:  # pragma: no cover – unsupported host
            self._log.info("NVML initialisation failed – GPU monitoring disabled: %s", exc)
            self._handle = None

    def _loop(self) -> None:  # pragma: no cover – real runtime path
        interval = float(self._cfg.get("gpu_monitor_interval_sec", 5))
        while not self._stop_evt.wait(interval):
            self._check_once()

    def _check_once(self) -> None:
        if self._handle is None:
            return  # Monitoring disabled
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)  # type: ignore[attr-defined]
            free_mb = mem.free / (1024 * 1024)
        except Exception as exc:  # pragma: no cover – NVML runtime error
            self._log.debug("nvmlDeviceGetMemoryInfo failed: %s", exc)
            return

        threshold_mb = int(self._cfg.get("vram_unload_threshold_mb", 1024))
        if self._orch.model_loaded and free_mb < threshold_mb:
            self._log.warning(
                "Free VRAM %.0f MB below threshold %d MB – triggering auto-unload", free_mb, threshold_mb
            )
            try:
                self._orch.auto_unload_model()
            except Exception as exc:  # pragma: no cover – robustness
                self._log.error("Auto-unload request failed: %s", exc) 