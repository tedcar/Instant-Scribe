import sys
from types import ModuleType
import pathlib
import os

import pytest

# Ensure project root directory is on *sys.path* so local packages import
_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Lightweight *EngineResponse* stub so we avoid importing heavy dependencies
class EngineResponse:  # noqa: D401 – minimal stub
    def __init__(self, *, ok: bool, payload):
        self.ok = ok
        self.payload = payload

# ---------------------------------------------------------------------------
# Shared stub components (mirrors *tests/test_application_orchestrator.py*)
# ---------------------------------------------------------------------------

class _StubAudioStreamer:
    def __init__(self, *, config_manager, on_speech_start, on_speech_end, **_kw):  # noqa: D401 – stub
        self.started = False
    def start(self):  # noqa: D401 – stub
        self.started = True
    def stop(self):  # noqa: D401 – stub
        self.started = False

class _StubHotkey:
    def __init__(self, *_a, **_kw):
        self.started = False
    def start(self):
        self.started = True
        return True
    def stop(self):
        self.started = False

class _StubTray:
    def __init__(self, *_a, **_kw):
        self.started = False
    def start(self):
        self.started = True
        return True
    def stop(self):
        self.started = False

class _StubNotify:
    def __init__(self, *_, **__):
        self.pause_states = []
    def show_pause_state(self, paused: bool):
        self.pause_states.append(paused)
    def show_transcription(self, text: str, **_):
        pass
    def show_model_state(self, state: str):
        pass
    def show_recovery_prompt(self):
        pass

class _StubWorker:
    def __init__(self, *_, **__):
        self.started = False
    def start(self):
        self.started = True
    def stop(self, **_):
        self.started = False
    def transcribe(self, *_a, **_kw):
        return EngineResponse(ok=True, payload="stub")
    def unload_model(self, **_kw):
        return EngineResponse(ok=True, payload={})
    def load_model(self, **_kw):
        return EngineResponse(ok=True, payload={})

@pytest.fixture(autouse=True)
def _patch_components(monkeypatch):
    # Ensure *InstanceScrubber* base package exists so monkeypatch can target its submodules
    if "InstanceScrubber" not in sys.modules:
        import types
        sys.modules["InstanceScrubber"] = types.ModuleType("InstanceScrubber")

    # Ensure child submodules exist so monkeypatch traversal succeeds
    _base_pkg = sys.modules["InstanceScrubber"]
    for _sub in ("audio_listener", "hotkey_manager", "tray_app", "notification_manager", "transcription_worker", "spooler", "silence_pruner"):
        full_name = f"InstanceScrubber.{_sub}"
        if full_name not in sys.modules:
            sub_mod = ModuleType(full_name)
            sys.modules[full_name] = sub_mod
            setattr(_base_pkg, _sub, sub_mod)
        else:
            sub_mod = sys.modules[full_name]
        if _sub == "transcription_worker":
            # Inject *EngineResponse* so orchestrator import succeeds
            if not hasattr(sub_mod, "EngineResponse"):
                sub_mod.EngineResponse = EngineResponse  # type: ignore[attr-defined]
        elif _sub == "spooler":
            if not hasattr(sub_mod, "AudioSpooler"):
                class _StubSpooler:  # noqa: D401 – minimal stub
                    def __init__(self, *_, **__):
                        pass
                    def start_session(self):
                        pass
                    def write_chunk(self, *_):
                        pass
                    def close_session(self, **_):
                        pass
                    @classmethod
                    def incomplete_session_exists(cls):
                        return False
                sub_mod.AudioSpooler = _StubSpooler  # type: ignore[attr-defined]
        elif _sub == "silence_pruner":
            if not hasattr(sub_mod, "prune_pcm_bytes"):
                def _noop(data, *_, **__):
                    return data
                sub_mod.prune_pcm_bytes = _noop  # type: ignore[attr-defined]

    monkeypatch.setattr("InstanceScrubber.audio_listener.AudioStreamer", _StubAudioStreamer, raising=False)
    monkeypatch.setattr("InstanceScrubber.hotkey_manager.HotkeyManager", _StubHotkey, raising=False)
    monkeypatch.setattr("InstanceScrubber.tray_app.TrayApp", _StubTray, raising=False)
    monkeypatch.setattr("InstanceScrubber.notification_manager.NotificationManager", _StubNotify, raising=False)
    monkeypatch.setattr("InstanceScrubber.transcription_worker.TranscriptionWorker", _StubWorker, raising=False)

    # Lightweight pystray stub (same as prior test)
    stub_pystray = ModuleType("pystray")
    class _StubMenu(tuple):
        SEPARATOR = object()
        def __new__(cls, *items):
            return super().__new__(cls, items)
    class _StubMenuItem:
        def __init__(self, text, action=None, enabled=True):
            self._text = text
            self.action = action
            self.enabled = enabled
        def __call__(self, _=None):
            return self._text(_) if callable(self._text) else self._text
    class _StubIcon:
        def __init__(self, name, icon, title, menu):
            pass
        def run(self):
            pass
        def stop(self):
            pass
        def update_menu(self):
            pass
    stub_pystray.Menu = _StubMenu  # type: ignore[attr-defined]
    stub_pystray.MenuItem = _StubMenuItem  # type: ignore[attr-defined]
    stub_pystray.Icon = _StubIcon  # type: ignore[attr-defined]
    sys.modules["pystray"] = stub_pystray
    yield

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pause_resume_cycle(tmp_path, monkeypatch):
    """Ensure pause/resume toggles AudioStreamer state and persists flag."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    from instant_scribe.application_orchestrator import ApplicationOrchestrator

    orch = ApplicationOrchestrator(use_stub_worker=True)
    orch.start()

    # Initial assumptions
    assert orch.is_listening is True
    assert orch.is_paused is False
    assert orch.audio_streamer.started is True  # type: ignore[attr-defined]

    # Pause
    orch._toggle_pause()  # pylint: disable=protected-access
    assert orch.is_paused is True
    assert orch.audio_streamer.started is False  # type: ignore[attr-defined]
    # Notification should have been shown
    assert orch.notification_manager.pause_states == [True]

    # Resume
    orch._toggle_pause()  # pylint: disable=protected-access
    assert orch.is_paused is False
    assert orch.audio_streamer.started is True  # type: ignore[attr-defined]
    assert orch.notification_manager.pause_states == [True, False]

    # Config should reflect final pause state (False)
    assert orch.config.get("paused") is False

    orch.shutdown() 