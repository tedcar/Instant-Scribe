import inspect
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Replicate minimal stubs locally to avoid inter-test import issues


class _StubAudioStreamer:
    def __init__(self, *, config_manager, on_speech_start, on_speech_end, **_kw):
        self._on_start = on_speech_start
        self._on_end = on_speech_end

    def start(self):
        pass

    def stop(self):
        pass

    def simulate_speech(self, payload: bytes = b"stub"):
        self._on_start()
        self._on_end(payload)


class _StubHotkey:
    def start(self):
        return True

    def stop(self):
        pass


class _StubTray:
    def start(self):
        return True

    def stop(self):
        pass


class _StubNotify:
    def __init__(self, *_, **__):
        self.recovery_prompts = 0

    def show_transcription(self, *_a, **_kw):
        pass

    def show_model_state(self, *_):
        pass

    def show_recovery_prompt(self):
        self.recovery_prompts += 1


from InstanceScrubber.transcription_worker import EngineResponse


class _StubWorker:
    def start(self):
        pass

    def stop(self, **_):
        pass

    def transcribe(self, *_a, **_kw):
        return EngineResponse(ok=True, payload="stub")

    def unload_model(self, **_):
        return EngineResponse(ok=True, payload={})

    def load_model(self, **_):
        return EngineResponse(ok=True, payload={})


@pytest.fixture(autouse=True)
def _patch_components(monkeypatch):
    """Patch heavy sub-components with local stubs."""
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


def test_orchestrator_spooler_lifecycle(tmp_path, monkeypatch):
    """Spooler should write files during speech and clean up on shutdown."""
    monkeypatch.setenv("APPDATA", str(tmp_path))

    from instant_scribe.application_orchestrator import ApplicationOrchestrator

    orch = ApplicationOrchestrator(use_stub_worker=True)
    orch.start()

    # Simulate a speech segment of 100 bytes
    assert hasattr(orch.audio_streamer, "simulate_speech")
    orch.audio_streamer.simulate_speech(b"x" * 100)

    temp_dir = tmp_path / "Instant Scribe" / "temp"
    # Chunk file should exist after speech
    assert any(temp_dir.glob("chunk_*.pcm"))

    # Now stop listening which should cleanup
    orch._toggle_listening()  # pylint: disable=protected-access
    assert not temp_dir.exists()

    orch.shutdown()


def test_recovery_prompt_called(tmp_path, monkeypatch):
    """On startup with leftover chunks the orchestrator must invoke recovery prompt."""
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # Create leftover chunk
    temp_dir = tmp_path / "Instant Scribe" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "chunk_0001.pcm").write_bytes(b"leftover")

    from instant_scribe.application_orchestrator import ApplicationOrchestrator

    orch = ApplicationOrchestrator(use_stub_worker=True, auto_start=False)

    # The patched _StubNotify increments counter on show_recovery_prompt
    notify = orch.notification_manager
    assert notify.recovery_prompts == 1

    orch.shutdown() 