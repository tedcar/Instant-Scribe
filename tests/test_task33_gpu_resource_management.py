import inspect
import sys
from pathlib import Path
from types import ModuleType

import pytest
import importlib

# ---------------------------------------------------------------------------
# Ensure repository root on sys.path
# ---------------------------------------------------------------------------
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ---------------------------------------------------------------------------
# Lightweight *pynvml* stub – exposes mutable *free_bytes* for runtime control
# ---------------------------------------------------------------------------

class _StubPynvml(ModuleType):
    def __init__(self):
        super().__init__("pynvml")
        self.free_bytes = 2 * 1024 * 1024 * 1024  # 2 GB default

    # NVML public API subset -------------------------------------------------
    def nvmlInit(self):  # noqa: D401 – stub
        pass

    def nvmlDeviceGetHandleByIndex(self, index):  # noqa: D401 – stub
        return index  # opaque handle

    class _MemInfo:  # pylint: disable=too-few-public-methods
        def __init__(self, free):
            self.free = free
            self.total = 8 * 1024 * 1024 * 1024  # 8 GB
            self.used = self.total - self.free

    def nvmlDeviceGetMemoryInfo(self, handle):  # noqa: D401 – stub
        return self._MemInfo(self.free_bytes)


# Inject stub into *sys.modules* **before** importing production code.
sys.modules["pynvml"] = _StubPynvml()

# Ensure *InstanceScrubber.gpu_monitor* picks up the new stub – if the module
# was already imported by previous tests we must reload it so the global
# ``_NVML_AVAILABLE`` flag is recalculated.
if "InstanceScrubber.gpu_monitor" in sys.modules:
    importlib.reload(sys.modules["InstanceScrubber.gpu_monitor"])
else:
    importlib.import_module("InstanceScrubber.gpu_monitor")

# ---------------------------------------------------------------------------
# Re-use minimal stubs for heavy components (audio, hotkeys, tray, etc.)
# ---------------------------------------------------------------------------

class _NoOp:
    def __init__(self, *_, **__):
        self.started = False

    def start(self):  # noqa: D401 – stub
        self.started = True
        return True

    def stop(self, *_, **__):  # noqa: D401 – stub
        self.started = False


class _StubNotify:
    def __init__(self, *_, **__):
        self.model_states = []

    def show_model_state(self, state: str):  # noqa: D401 – stub
        self.model_states.append(state)

    def show_pause_state(self, *_):
        pass


from InstanceScrubber.transcription_worker import EngineResponse


class _StubWorker:
    def __init__(self, *_, **__):
        self.unload_called = 0

    def start(self):
        pass

    def stop(self, **_):
        pass

    def unload_model(self, **__) -> EngineResponse:
        self.unload_called += 1
        return EngineResponse(ok=True, payload={"state": "unloaded"})

    def load_model(self, **__) -> EngineResponse:
        return EngineResponse(ok=True, payload={"state": "loaded"})


@pytest.fixture(autouse=True)
def _patch_components(monkeypatch):
    """Patch heavy sub-components with simple no-op stubs."""
    monkeypatch.setattr("InstanceScrubber.audio_listener.AudioStreamer", _NoOp, raising=True)
    monkeypatch.setattr("InstanceScrubber.hotkey_manager.HotkeyManager", _NoOp, raising=True)
    monkeypatch.setattr("InstanceScrubber.tray_app.TrayApp", _NoOp, raising=True)
    monkeypatch.setattr("InstanceScrubber.notification_manager.NotificationManager", _StubNotify, raising=True)
    monkeypatch.setattr("InstanceScrubber.transcription_worker.TranscriptionWorker", _StubWorker, raising=True)
    yield


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_auto_unload_when_vram_low(monkeypatch):
    """GPUResourceMonitor triggers *auto_unload_model* when free VRAM < threshold."""
    from instant_scribe.application_orchestrator import ApplicationOrchestrator

    orch = ApplicationOrchestrator(use_stub_worker=True)
    orch.start()

    # Access stub pynvml via sys.modules and reduce free memory below threshold.
    stub_nvml = sys.modules["pynvml"]
    stub_nvml.free_bytes = 100 * 1024 * 1024  # 100 MB – below 1 GB default threshold

    # Force a single manual poll so the test is deterministic.
    orch.gpu_monitor.check_once()

    # Expect model to be auto-unloaded exactly once.
    assert orch.model_loaded is False
    worker: _StubWorker = orch.worker  # type: ignore[assignment]
    assert worker.unload_called == 1

    # Notification should have been sent.
    notify: _StubNotify = orch.notification_manager  # type: ignore[assignment]
    assert notify.model_states[-1] == "unloaded"

    orch.shutdown() 