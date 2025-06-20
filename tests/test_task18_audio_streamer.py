"""AudioStreamer start/stop cycle using a *stub* PyAudio backend.

This fills in coverage for the microphone capture logic without requiring
actual hardware or the native *pyaudio* wheels in the test environment.
"""

from __future__ import annotations

import types

import numpy as np
import pytest

import InstanceScrubber.audio_listener as al


class _DummyStream:  # pylint: disable=too-few-public-methods
    def __init__(self, cb):
        self._active = False
        self._cb = cb

    def start_stream(self):  # noqa: D401 – stub
        self._active = True
        # Feed a single silent frame to the callback so that basic VAD path
        # is executed during the *start()* call.
        self._cb((np.zeros(480, dtype=np.int16)).tobytes(), None, None, None)

    def stop_stream(self):  # noqa: D401 – stub
        self._active = False

    def close(self):  # noqa: D401 – stub
        pass

    def is_active(self):  # noqa: D401 – stub
        return self._active


class _DummyPyAudio:  # pylint: disable=too-few-public-methods
    paInt16 = 8  # value is irrelevant – just for attribute presence
    paContinue = 0

    def open(self, *_, **kwargs):  # noqa: D401 – stub
        return _DummyStream(kwargs["stream_callback"])

    def terminate(self):  # noqa: D401 – stub
        pass


class _Cfg:  # pylint: disable=too-few-public-methods
    """Very small config stub satisfying *get* interface."""

    def get(self, _key, default=None):  # noqa: D401 – stub
        return default


def test_audio_streamer_start_stop(monkeypatch):
    """`start()` should create a stream and `stop()` should terminate it."""

    # Patch the *pyaudio* module inside the target module to our stub.
    dummy_pyaudio = types.ModuleType("pyaudio")
    dummy_pyaudio.PyAudio = _DummyPyAudio  # type: ignore[attr-defined]
    dummy_pyaudio.paInt16 = _DummyPyAudio.paInt16  # type: ignore[attr-defined]
    dummy_pyaudio.paContinue = _DummyPyAudio.paContinue  # type: ignore[attr-defined]
    monkeypatch.setattr(al, "pyaudio", dummy_pyaudio, raising=False)

    # Also patch *webrtcvad* with a trivial implementation that always
    # returns *False* so that no speech is detected during the test.
    class _FakeVad:  # pylint: disable=too-few-public-methods
        def __init__(self, *_a, **_kw):
            pass
        def is_speech(self, *_a, **_kw):  # noqa: D401 – stub
            return False
    fake_webrtcvad = types.ModuleType("webrtcvad")
    fake_webrtcvad.Vad = _FakeVad  # type: ignore[attr-defined]
    monkeypatch.setattr(al, "webrtcvad", fake_webrtcvad, raising=False)

    streamer = al.AudioStreamer(config_manager=_Cfg(), on_speech_start=lambda: None, on_speech_end=lambda _d: None)

    streamer.start()
    assert streamer._stream is not None  # pylint: disable=protected-access
    assert streamer._stream.is_active()

    streamer.stop()
    assert streamer._stream is None  # pylint: disable=protected-access 