"""Realtime audio capture & Voice Activity Detection (VAD) gate.

This module fulfils *DEV_TASKS.md – Task 4* requirements:

4.1 ``AudioStreamer`` class opening a PyAudio microphone stream (blueprint §3.1.1).
4.2 WebRTC VAD‐powered state-machine with ``on_speech_start`` / ``on_speech_end`` events.
4.3 Aggressiveness & silence‐threshold parameters are read from :class:`InstanceScrubber.config_manager.ConfigManager`.

Unit-tests exercise the VAD gate logic via dependency-injection (no hardware required).
"""

from __future__ import annotations

import logging
import math
import threading
from typing import Callable, Optional

try:
    import pyaudio  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – optional at runtime / in CI
    pyaudio = None  # type: ignore

try:
    import webrtcvad  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – fallback stub for test environments

    class _StubVad:  # pylint: disable=too-few-public-methods
        """Fallback *no-op* VAD when *webrtcvad* wheel unavailable.

        The *is_speech()* method always returns ``False`` ensuring predictable
        behaviour in test runners lacking the native extension.
        """

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def is_speech(self, _frame: bytes, _sample_rate: int) -> bool:  # noqa: D401 – simple stub
            return False

    webrtcvad = type("_webrtcvad", (), {"Vad": _StubVad})()  # type: ignore

# ---------------------------------------------------------------------------
# VAD state-machine – can be unit-tested without real audio
# ---------------------------------------------------------------------------


class VADAudioGate:
    """Voice Activity Detection gate implementing a simple *speech ↔ silence* FSM.

    The gate processes raw PCM frames (matching *webrtcvad* requirements) and
    invokes callback functions when speech begins and ends.  All timing is
    derived from frame size, resulting in deterministic behaviour regardless of
    wall-clock timing or buffering strategy.
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16_000,
        frame_duration_ms: int = 30,
        vad_aggressiveness: int = 2,
        silence_threshold_ms: int = 700,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        if frame_duration_ms not in (10, 20, 30):
            raise ValueError("frame_duration_ms must be 10, 20 or 30 ms for webrtcvad")

        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.bytes_per_frame = int(self.sample_rate * (self.frame_duration_ms / 1000) * 2)  # 16-bit mono

        self._vad = webrtcvad.Vad(vad_aggressiveness)

        self._silence_frames_required = max(1, math.ceil(silence_threshold_ms / frame_duration_ms))
        self._on_start = on_speech_start or (lambda: None)
        self._on_end = on_speech_end or (lambda _data: None)

        self._in_speech: bool = False
        self._silence_counter: int = 0
        self._buffer = bytearray()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, frame: bytes) -> None:
        """Feed a single *frame* of PCM audio into the gate.

        The frame **must**:
        • be encoded as 16-bit little-endian PCM;
        • have length exactly *bytes_per_frame*.
        """
        if len(frame) != self.bytes_per_frame:
            raise ValueError(
                f"Invalid frame length {len(frame)} bytes – expected {self.bytes_per_frame}")

        is_voiced = self._vad.is_speech(frame, self.sample_rate)

        if self._in_speech:
            self._buffer.extend(frame)
            if is_voiced:
                self._silence_counter = 0  # reset on continued speech
            else:
                self._silence_counter += 1
                if self._silence_counter >= self._silence_frames_required:
                    # End of utterance detected
                    logging.debug("VAD → speech_end (buffer=%d bytes)", len(self._buffer))
                    self._in_speech = False
                    self._on_end(bytes(self._buffer))
                    # Reset state for next utterance
                    self._buffer.clear()
                    self._silence_counter = 0
        else:  # currently in SILENT state
            if is_voiced:
                logging.debug("VAD → speech_start")
                self._in_speech = True
                self._buffer.extend(frame)
                self._on_start()


# ---------------------------------------------------------------------------
# High-level microphone streamer
# ---------------------------------------------------------------------------


class AudioStreamer:
    """Microphone audio capture feeding the :class:`VADAudioGate` in real-time."""

    def __init__(
        self,
        *,
        config_manager,  # "Any" to avoid circular import in hints
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[bytes], None]] = None,
        frame_duration_ms: int = 30,
        sample_rate: int = 16_000,
    ) -> None:
        self._config = config_manager
        self._frame_duration_ms = frame_duration_ms
        self._sample_rate = sample_rate

        self._vad_gate = VADAudioGate(
            sample_rate=sample_rate,
            frame_duration_ms=frame_duration_ms,
            vad_aggressiveness=int(self._config.get("vad_aggressiveness", 2)),
            silence_threshold_ms=int(self._config.get("silence_threshold_ms", 700)),
            on_speech_start=on_speech_start,
            on_speech_end=on_speech_end,
        )

        self._pyaudio_instance = None  # created lazily to avoid module requirement in tests
        self._stream = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open the microphone stream and begin processing audio frames."""
        if pyaudio is None:  # pragma: no cover – runtime dependency absent
            raise RuntimeError(
                "pyaudio module not available – microphone capture cannot be started")

        with self._lock:
            if self._stream and self._stream.is_active():
                logging.debug("AudioStreamer already running – start() ignored")
                return

            self._pyaudio_instance = pyaudio.PyAudio()  # type: ignore[arg-type]

            frames_per_buffer = int(
                self._sample_rate * (self._frame_duration_ms / 1000))

            self._stream = self._pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=frames_per_buffer,
                stream_callback=self._pyaudio_callback,
            )
            self._stream.start_stream()
            logging.info("Microphone stream started (rate=%d Hz, frame=%d ms)",
                         self._sample_rate, self._frame_duration_ms)

    def stop(self) -> None:
        """Stop and close the microphone stream."""
        with self._lock:
            if not self._stream:
                return
            self._stream.stop_stream()
            self._stream.close()
            if self._pyaudio_instance:
                self._pyaudio_instance.terminate()
            self._stream = None
            self._pyaudio_instance = None
            logging.info("Microphone stream stopped")

    # ------------------------------------------------------------------
    # Internal PyAudio callback
    # ------------------------------------------------------------------

    def _pyaudio_callback(self, in_data, _frame_count, _time_info, _status):  # noqa: D401 – PyAudio API
        try:
            self._vad_gate.process_frame(in_data)
        except Exception as exc:  # pragma: no cover – safety
            logging.exception("Error in audio processing callback: %s", exc)
        return (None, pyaudio.paContinue)  # type: ignore

    # ------------------------------------------------------------------
    # Context-manager helpers for convenience "with" usage
    # ------------------------------------------------------------------

    def __enter__(self):  # noqa: D401 – context manager boilerplate
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: D401 – context manager boilerplate
        self.stop()
        return False  # propagate exceptions


__all__ = [
    "VADAudioGate",
    "AudioStreamer",
] 