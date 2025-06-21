import inspect
import sys
from pathlib import Path
from types import ModuleType

import pytest

# ---------------------------------------------------------------------------
# Ensure repository root is on sys.path
# ---------------------------------------------------------------------------
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ---------------------------------------------------------------------------
# Stub heavy-weight dependencies *before* importing the orchestrator.
# ---------------------------------------------------------------------------

# 1. Stub AudioStreamer so we do not touch real microphone / pyaudio
class _StubAudioStreamer:
    def __init__(self, *, config_manager, on_speech_start, on_speech_end, **_kw):  # noqa: D401
        self._on_start = on_speech_start
        self._on_end = on_speech_end
        self.started = False

    def start(self):  # noqa: D401 – stub
        self.started = True

    def stop(self):  # noqa: D401 – stub
        self.started = False

    # Helper that tests can call to emulate speech capture
    def simulate_speech(self, payload: bytes = b"stub"):
        self._on_start()
        self._on_end(payload)


# 2. Stub HotkeyManager – no-op
class _StubHotkey:
    def __init__(self, *_a, **_kw):  # noqa: D401 – stub
        self.started = False

    def start(self):  # noqa: D401 – stub
        self.started = True
        return True

    def stop(self):  # noqa: D401 – stub
        self.started = False


# 3. Stub TrayApp – no GUI
class _StubTray:
    def __init__(self, *_a, **_kw):  # noqa: D401 – stub
        self.started = False

    def start(self):  # noqa: D401 – stub
        self.started = True
        return True

    def stop(self):  # noqa: D401 – stub
        self.started = False


# 4. Stub NotificationManager – record shown messages
class _StubNotify:
    def __init__(self, *_, **__):  # noqa: D401 – stub
        self.messages = []
        self.model_states = []
        self.recovery_prompts = 0
        # Task 25 – track pause/resume notifications
        self.pause_states = []

    def show_transcription(self, text: str, **_):  # noqa: D401 – signature match
        self.messages.append(text)

    def show_model_state(self, state: str):  # noqa: D401 – stub
        self.model_states.append(state)

    def show_recovery_prompt(self):  # noqa: D401 – stub
        self.recovery_prompts += 1

    # Task 25 – stub pause notifications
    def show_pause_state(self, paused: bool):  # noqa: D401 – stub
        self.pause_states.append(paused)


# 5. Stub TranscriptionWorker – instant response
from InstanceScrubber.transcription_worker import EngineResponse


class _StubWorker:
    def __init__(self, *_, **__):  # noqa: D401 – stub
        self.started = False

    def start(self):  # noqa: D401 – stub
        self.started = True

    def stop(self, **_):  # noqa: D401 – stub
        self.started = False

    def transcribe(self, audio_pcm: bytes, **__) -> EngineResponse:  # noqa: D401 – stub
        # Return deterministic payload regardless of input
        return EngineResponse(ok=True, payload="stub transcript")

    # VRAM toggle stubs
    def unload_model(self, **__) -> EngineResponse:  # noqa: D401 – stub
        return EngineResponse(ok=True, payload={"state": "unloaded"})

    def load_model(self, **__) -> EngineResponse:  # noqa: D401 – stub
        return EngineResponse(ok=True, payload={"state": "loaded"})


@pytest.fixture(autouse=True)
def _patch_components(monkeypatch):
    """Patch heavy sub-components with stubs for every test in this module."""
    monkeypatch.setattr(
        "InstanceScrubber.audio_listener.AudioStreamer",
        _StubAudioStreamer,
        raising=True,
    )
    monkeypatch.setattr(
        "InstanceScrubber.hotkey_manager.HotkeyManager",
        _StubHotkey,
        raising=True,
    )
    monkeypatch.setattr(
        "InstanceScrubber.tray_app.TrayApp",
        _StubTray,
        raising=True,
    )
    monkeypatch.setattr(
        "InstanceScrubber.notification_manager.NotificationManager",
        _StubNotify,
        raising=True,
    )
    monkeypatch.setattr(
        "InstanceScrubber.transcription_worker.TranscriptionWorker",
        _StubWorker,
        raising=True,
    )
    yield


# ---------------------------------------------------------------------------
# Lightweight *pystray* stub – shared with TrayApp tests so importing the
# production module never touches the real system APIs.
# ---------------------------------------------------------------------------

stub_pystray = ModuleType("pystray")

class _StubMenu(tuple):
    SEPARATOR = object()
    def __new__(cls, *items):
        return super().__new__(cls, items)

after_stub_menu_placeholder = None

class _StubMenuItem:
    def __init__(self, text, action=None, enabled=True):
        self._text = text
        self.action = action
        self.enabled = enabled
    def __call__(self, _=None):
        return self._text(_) if callable(self._text) else self._text

class _StubIcon:
    def __init__(self, name, icon, title, menu):
        self.name = name
        self.icon = icon
        self.title = title
        self.menu = menu
        self.updated = False
    def run(self):
        pass
    def stop(self):
        pass
    def update_menu(self):
        self.updated = True

stub_pystray.Menu = _StubMenu  # type: ignore[attr-defined]
stub_pystray.MenuItem = _StubMenuItem  # type: ignore[attr-defined]
stub_pystray.Icon = _StubIcon  # type: ignore[attr-defined]

sys.modules["pystray"] = stub_pystray


def test_end_to_end_transcription(tmp_path, monkeypatch):
    """Audio -> worker -> notification happy path."""
    # Redirect CWD so crash/log files don't leak into the repo.
    monkeypatch.chdir(tmp_path)

    from instant_scribe.application_orchestrator import ApplicationOrchestrator

    orchestrator = ApplicationOrchestrator(use_stub_worker=True)
    orchestrator.start()

    # Access patched audio streamer and simulate speech
    assert isinstance(orchestrator.audio_streamer, _StubAudioStreamer)
    orchestrator.audio_streamer.simulate_speech(b"hello")

    # The stub NotificationManager should have been invoked with the transcript
    notify = orchestrator.notification_manager
    assert isinstance(notify, _StubNotify)
    assert notify.messages == ["stub transcript"]

    orchestrator.shutdown()


def test_sys_excepthook_writes_crash_log(tmp_path, monkeypatch):
    """The global excepthook installed by the orchestrator writes crash.log."""
    monkeypatch.chdir(tmp_path)

    from instant_scribe.application_orchestrator import ApplicationOrchestrator

    orch = ApplicationOrchestrator(use_stub_worker=True)

    # Simulate an unhandled exception – we call the hook directly.
    try:
        raise ValueError("kaboom")
    except ValueError as exc:
        exc_type, exc_val, exc_tb = sys.exc_info()
        orch._handle_exception(exc_type, exc_val, exc_tb)  # pylint: disable=protected-access

    log_file = Path("logs/crash.log")
    assert log_file.is_file()
    content = log_file.read_text(encoding="utf-8")
    assert "ValueError" in content and "kaboom" in content 