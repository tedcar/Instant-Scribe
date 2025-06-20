# Orchestrator module orchestrating all sub-components of Instant Scribe.
#
# This file fulfils *DEV_TASKS.md – Task 10* (Application Orchestrator):
#   10.1 Main script spinning up threads / processes & event-loop
#   10.2 Graceful shutdown – flush queues, stop audio, join processes
#   10.3 Global sys.excepthook → logs/crash.log
#
# The implementation purposefully keeps external-resource heavy components
# (microphone, GPU model, system-tray, etc.) optional so that the orchestrator
# remains importable and testable on any CI runner.  All interactions are
# wrapped in *try/except* with detailed logging in order to guarantee a
# best-effort user-experience even when a particular subsystem is unavailable
# (e.g. missing PyAudio on Linux, headless server lacking WinRT APIs, …).

from __future__ import annotations

import logging
import signal
import sys
import threading
import traceback
from pathlib import Path
from types import TracebackType
from typing import Any, Type

# --- Local project imports --------------------------------------------------
from instant_scribe.config_manager import ConfigManager  # idempotent – fast
from instant_scribe.logging_config import setup_logging  # noqa: F401 – side-effect only (root logger)

# *InstanceScrubber* hosts the bulk of heavy-weight sub-modules.
from InstanceScrubber.audio_listener import AudioStreamer
from InstanceScrubber.hotkey_manager import HotkeyManager
from InstanceScrubber.notification_manager import NotificationManager
from InstanceScrubber.tray_app import TrayApp
from InstanceScrubber.transcription_worker import (
    EngineResponse,
    TranscriptionWorker,
)

__all__ = [
    "ApplicationOrchestrator",
    "main",
]


class _ConfigKeyAdapter:  # pylint: disable=too-few-public-methods
    """Light wrapper exposing a *single* config key as *hotkey* for reuse by
    :class:`InstanceScrubber.hotkey_manager.HotkeyManager`.

    The adapter delegates *get* / *set* / *reload* to the underlying
    :class:`instant_scribe.config_manager.ConfigManager` instance but maps the
    requested key to an alternative (e.g. *model_hotkey*).  This avoids any
    changes to the `HotkeyManager` implementation while still supporting
    multiple distinct hotkey bindings.
    """

    def __init__(self, base_cfg: ConfigManager, mapped_key: str):
        self._cfg = base_cfg
        self._key = mapped_key

    # -- Dict-like interface expected by HotkeyManager ------------------
    def get(self, key, default=None):  # noqa: D401 – signature match
        if key == "hotkey":
            return self._cfg.get(self._key, default)
        return self._cfg.get(key, default)

    def set(self, key, value, *, auto_save=True):  # noqa: D401
        if key == "hotkey":
            self._cfg.set(self._key, value, auto_save=auto_save)
        else:
            self._cfg.set(key, value, auto_save=auto_save)

    def reload(self):  # noqa: D401 – proxy
        self._cfg.reload()


class ApplicationOrchestrator:  # pylint: disable=too-many-instance-attributes
    """High-level *application orchestrator* tying all components together."""

    _CRASH_LOG_PATH = Path("logs/crash.log")

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def __init__(self, *, use_stub_worker: bool = False, auto_start: bool = False):
        self._log = logging.getLogger(self.__class__.__name__)

        # Public-ish state toggled by UI callbacks / tests
        self.is_listening: bool = False
        self._is_running: bool = False
        self._lock = threading.Lock()

        # Core singletons -------------------------------------------------
        self.config = ConfigManager()
        self.worker = TranscriptionWorker(use_stub=use_stub_worker)
        self.notification_manager = NotificationManager(
            copy_on_click=self.config.get("copy_to_clipboard_on_click", True),
            show_notifications=self.config.get("show_notifications", True),
        )
        self.audio_streamer = AudioStreamer(
            config_manager=self.config,
            on_speech_start=self._on_speech_start,
            on_speech_end=self._on_speech_end,
        )
        self.hotkey_manager = HotkeyManager(self.config, on_activate=self._toggle_listening)

        # VRAM toggle hotkey (Ctrl+Alt+F6)
        vram_cfg_adapter = _ConfigKeyAdapter(self.config, "model_hotkey")
        self.vram_hotkey_manager = HotkeyManager(
            vram_cfg_adapter,
            on_activate=self._toggle_model_vram,
        )

        # Track current model residency state – starts *loaded* because the
        # worker loads the model during *start()*.
        self._model_loaded: bool = True
        self.tray_app = TrayApp(
            self.config,
            on_toggle_listening=self._toggle_listening,
            on_exit=self.shutdown,
        )

        # Install global unhandled-exception hook *before* anything starts so
        # we never miss a traceback.
        self._install_excepthook()

        # Handle SIGINT / SIGTERM for graceful Ctrl-C & service shutdown.
        try:
            signal.signal(signal.SIGINT, self._handle_signal)  # noqa: B904 – Windows compatible
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, self._handle_signal)
        except ValueError:  # signal already set from within thread – ignore
            pass

        if auto_start:
            self.start()

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------
    def start(self) -> None:  # noqa: D401 – imperative API
        """Initialise & start all sub-components (idempotent)."""
        if self._is_running:
            return

        self._log.info("Application starting …")

        # Spawn transcription worker (GPU heavy – do first).
        self.worker.start()

        # UI / I-O layers are best-effort – log but continue on failure.
        try:
            if not self.hotkey_manager.start():
                self._log.warning("Global hotkey unavailable – user must rely on tray UI")
        except Exception as exc:  # pylint: disable=broad-except
            self._log.warning("Hotkey manager failed: %s", exc)

        # Start the VRAM toggle hotkey – failure is non-fatal.
        try:
            if not self.vram_hotkey_manager.start():
                self._log.warning("VRAM toggle hotkey unavailable – model must be managed via UI/API")
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug("VRAM hotkey init error: %s", exc)

        try:
            if not self.tray_app.start():
                self._log.info("System-tray UI disabled (headless environment)")
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug("Tray UI initialisation error: %s", exc)

        # Start microphone listener (may raise if PyAudio missing).
        try:
            self.audio_streamer.start()
            self.is_listening = True
        except Exception as exc:  # pylint: disable=broad-except
            self._log.warning("Audio streamer unavailable – running in *idle* mode: %s", exc)
            self.is_listening = False

        self._is_running = True
        self._log.info("Application started (listening=%s)", self.is_listening)

    # .................................................................
    def shutdown(self) -> None:  # noqa: D401 – imperative API
        """Attempt graceful shutdown of all subsystems."""
        if not self._is_running:
            return

        self._log.info("Shutting down …")

        # Order matters – stop producer of new work first.
        try:
            self.audio_streamer.stop()
        except Exception:  # pragma: no cover – best-effort
            pass

        try:
            self.hotkey_manager.stop()
        except Exception:
            pass

        try:
            self.vram_hotkey_manager.stop()
        except Exception:
            pass

        try:
            self.tray_app.stop()
        except Exception:
            pass

        try:
            self.worker.stop(reason="app shutdown")
        except Exception:
            pass

        self._is_running = False
        self._log.info("Shutdown complete")

    # ------------------------------------------------------------------
    # UI callbacks & internal handlers
    # ------------------------------------------------------------------
    def _toggle_listening(self) -> None:  # noqa: D401 – imperative API
        """Hotkey / tray-menu callback – start/stop microphone listener."""
        with self._lock:
            if self.is_listening:
                try:
                    self.audio_streamer.stop()
                    self.is_listening = False
                    self._log.info("Listening stopped via user toggle")
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.warning("Unable to stop listener: %s", exc)
            else:
                try:
                    self.audio_streamer.start()
                    self.is_listening = True
                    self._log.info("Listening started via user toggle")
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.error("Failed to start listener: %s", exc)

    # .................................................................
    def _on_speech_start(self) -> None:
        self._log.debug("Speech segment started")

    def _on_speech_end(self, audio_bytes: bytes) -> None:
        self._log.debug("Speech segment finished –%d bytes", len(audio_bytes))
        try:
            resp: EngineResponse = self.worker.transcribe(audio_bytes, timeout=30)
            if resp.ok:
                text: str = str(resp.payload)
                self._log.info("Transcription succeeded: %s", text)
                self.notification_manager.show_transcription(text)
            else:
                self._log.error("Worker returned error: %s", resp.payload)
        except Exception as exc:  # pylint: disable=broad-except
            self._log.exception("Transcription failed: %s", exc)

    # ------------------------------------------------------------------
    # Exception / signal handling
    # ------------------------------------------------------------------
    def _install_excepthook(self) -> None:
        """Register *self._handle_exception* as the global sys.excepthook."""
        sys.excepthook = self._handle_exception  # type: ignore[assignment]

    # noinspection PyUnusedLocal
    def _handle_exception(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Write uncaught exceptions to *logs/crash.log* and console."""
        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

        try:
            self._CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self._CRASH_LOG_PATH.open("a", encoding="utf-8") as fh:
                traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
        except Exception:  # pragma: no cover – disk errors best-effort
            pass

    # .................................................................
    def _handle_signal(self, signum: int, _frame: Any) -> None:  # noqa: D401 – signal handler
        self._log.info("Signal %s received – initiating shutdown.", signum)
        self.shutdown()

    # .................................................................
    def _toggle_model_vram(self) -> None:
        """Callback bound to *Ctrl+Alt+F6* – unload/reload the ASR model."""

        with self._lock:
            if self._model_loaded:
                # Request unload
                try:
                    resp = self.worker.unload_model(timeout=30)
                    if resp.ok:
                        self._model_loaded = False
                        self.notification_manager.show_model_state("unloaded")
                        self._log.info("ASR model unloaded from VRAM")
                    else:
                        self._log.error("Unload model failed: %s", resp.payload)
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.error("Error unloading model: %s", exc)
            else:
                # Request load
                try:
                    resp = self.worker.load_model(timeout=120)
                    if resp.ok:
                        self._model_loaded = True
                        self.notification_manager.show_model_state("loaded")
                        self._log.info("ASR model loaded into VRAM")
                    else:
                        self._log.error("Load model failed: %s", resp.payload)
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.error("Error loading model: %s", exc)


# ---------------------------------------------------------------------------
# *console-script* entry-point
# ---------------------------------------------------------------------------

def main() -> None:  # noqa: D401 – script entry
    """Launch the orchestrator in *production* mode (real GPU model, etc.)."""
    ApplicationOrchestrator(use_stub_worker=False, auto_start=True)


if __name__ == "__main__":  # pragma: no cover – manual execution helper
    main() 