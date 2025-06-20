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
import importlib

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
from InstanceScrubber.spooler import AudioSpooler  # NEW – Task 12
from InstanceScrubber.silence_pruner import prune_pcm_bytes
from InstanceScrubber.gpu_monitor import GPUResourceMonitor

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
    def __init__(self, *, use_stub_worker: bool = False, auto_start: bool = False, force_recover: bool = False):
        self._log = logging.getLogger(self.__class__.__name__)

        # Public-ish state toggled by UI callbacks / tests
        self.is_listening: bool = False
        self._is_running: bool = False
        self._lock = threading.Lock()

        # Core singletons -------------------------------------------------
        self.config = ConfigManager()
        # Dynamically resolve components so *pytest* monkeypatches are honoured
        AudioStreamerCls = importlib.import_module("InstanceScrubber.audio_listener").AudioStreamer
        HotkeyManagerCls = importlib.import_module("InstanceScrubber.hotkey_manager").HotkeyManager
        NotificationManagerCls = importlib.import_module("InstanceScrubber.notification_manager").NotificationManager
        TranscriptionWorkerCls = importlib.import_module("InstanceScrubber.transcription_worker").TranscriptionWorker
        TrayAppCls = importlib.import_module("InstanceScrubber.tray_app").TrayApp

        def _safe_init(cls, *args, **kwargs):  # noqa: D401 – local util
            try:
                return cls(*args, **kwargs)
            except TypeError:
                try:
                    return cls(*args)
                except TypeError:
                    return cls()

        try:
            self.worker = TranscriptionWorkerCls(use_stub=use_stub_worker)
        except TypeError:  # Stub worker may not accept kwarg
            self.worker = TranscriptionWorkerCls()
        self.notification_manager = NotificationManagerCls(
            copy_on_click=self.config.get("copy_to_clipboard_on_click", True),
            show_notifications=self.config.get("show_notifications", True),
        )
        self.audio_streamer = AudioStreamerCls(
            config_manager=self.config,
            on_speech_start=self._on_speech_start,
            on_speech_end=self._on_speech_end,
        )
        self.hotkey_manager = _safe_init(HotkeyManagerCls, self.config, on_activate=self._toggle_listening)

        # VRAM toggle hotkey (Ctrl+Alt+F6)
        vram_cfg_adapter = _ConfigKeyAdapter(self.config, "model_hotkey")
        self.vram_hotkey_manager = _safe_init(
            HotkeyManagerCls,
            vram_cfg_adapter,
            on_activate=self._toggle_model_vram,
        )

        # Task 25 – Pause / Resume workflow -----------------------------
        pause_cfg_adapter = _ConfigKeyAdapter(self.config, "pause_hotkey")
        self.pause_hotkey_manager = _safe_init(
            HotkeyManagerCls,
            pause_cfg_adapter,
            on_activate=self._toggle_pause,
        )

        # Track *pause* state persisted between sessions (Task 25.2)
        self.is_paused: bool = bool(self.config.get("paused", False))

        # Track current model residency state – starts *loaded* because the
        # worker loads the model during *start()*.
        self._model_loaded: bool = True
        self.tray_app = _safe_init(
            TrayAppCls,
            self.config,
            on_toggle_listening=self._toggle_listening,
            on_exit=self.shutdown,
        )

        # Task 33 – GPU VRAM monitoring
        self.gpu_monitor = GPUResourceMonitor(self, self.config, self.notification_manager)

        # Task 12 & 24 – persistent audio spooler with configurable chunk interval
        self.spooler = AudioSpooler(
            chunk_interval_sec=int(self.config.get("spooler_chunk_interval_sec", 60))
        )

        # On startup detect incomplete recording and notify user.
        try:
            if force_recover or AudioSpooler.incomplete_session_exists():
                # Leverage notification manager – falls back to log when not supported
                if hasattr(self.notification_manager, "show_recovery_prompt"):
                    self.notification_manager.show_recovery_prompt()
                else:
                    self._log.warning("Incomplete recording detected – recovery prompt method missing")
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug("Recovery detection failed: %s", exc)

        # Install global unhandled-exception hook from *crash_reporter* so we
        # never miss a traceback (DEV_TASKS – Task 32).
        from instant_scribe.crash_reporter import install as _install_crash_hook

        _install_crash_hook()
        # The legacy in-class excepthook has been replaced – we keep the
        # method stub for backward compatibility but it is no longer invoked.

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

        # Start the Pause / Resume hotkey (Task 25)
        try:
            if not self.pause_hotkey_manager.start():
                self._log.warning("Pause hotkey unavailable – user must rely on tray UI")
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug("Pause hotkey init error: %s", exc)

        try:
            if not self.tray_app.start():
                self._log.info("System-tray UI disabled (headless environment)")
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug("Tray UI initialisation error: %s", exc)

        # Only auto-start microphone if not paused at launch.
        try:
            if not self.is_paused:
                self.audio_streamer.start()
                # Task 12 – begin spooling chunks for this recording session
                self.spooler.start_session()
                self.is_listening = True
            else:
                self.is_listening = True  # Considered *listening* but paused
                self.notification_manager.show_pause_state(True)
        except Exception as exc:  # pylint: disable=broad-except
            self._log.warning("Audio streamer unavailable – running in *idle* mode: %s", exc)
            self.is_listening = False

        self._is_running = True
        self._log.info("Application started (listening=%s)", self.is_listening)

        # Start GPU monitor **after** successful start so the callback has
        # full access to running subsystems.
        try:
            self.gpu_monitor.start()
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug("GPU monitor failed to start: %s", exc)

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
            self.pause_hotkey_manager.stop()
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

        # Task 12 – ensure temp directory is cleaned on graceful exit
        try:
            self.spooler.close_session(success=True)
        except Exception:  # pragma: no cover
            pass

        # Task 33 – stop GPU monitor last since it may call back into worker
        try:
            self.gpu_monitor.stop()
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
                    # Task 12 – clean up tmp chunks on normal stop
                    self.spooler.close_session(success=True)
                    self.is_listening = False
                    # Reset pause state (Task 25)
                    self.is_paused = False
                    self.config.set("paused", False)
                    self._log.info("Listening stopped via user toggle")
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.warning("Unable to stop listener: %s", exc)
            else:
                try:
                    self.audio_streamer.start()
                    # Task 12 – begin spooling chunks for this recording session
                    self.spooler.start_session()
                    self.is_listening = True
                    self.is_paused = False  # Ensure paused flag reset
                    self.config.set("paused", False)
                    self._log.info("Listening started via user toggle")
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.error("Failed to start listener: %s", exc)

    # .................................................................
    def _on_speech_start(self) -> None:
        self._log.debug("Speech segment started")

    def _on_speech_end(self, audio_bytes: bytes) -> None:
        self._log.debug("Speech segment finished –%d bytes", len(audio_bytes))
        # Task 12 – persist segment to disk before heavy processing
        try:
            self.spooler.write_chunk(audio_bytes)
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug("Spooler write failed: %s", exc)
        # Task 22 – prune *long* silence segments (>2 min) before GPU inference
        try:
            threshold_ms = int(self.config.get("silence_prune_threshold_ms", 120_000))
            audio_bytes = prune_pcm_bytes(
                audio_bytes,
                sample_rate=16_000,
                threshold_ms=threshold_ms,
            )
        except Exception as exc:  # pylint: disable=broad-except
            # Defensive – pruning failure must never crash the recording path.
            self._log.debug("Silence pruning failed – falling back to raw audio: %s", exc)

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
    # Legacy behaviour – write to *logs/crash.log* relative to CWD so
    # existing tests continue to pass.
    def _handle_exception(  # pylint: disable=unused-argument
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_tb: "TracebackType | None",
    ) -> None:
        crash_path = Path("logs/crash.log")
        crash_path.parent.mkdir(parents=True, exist_ok=True)

        logging.critical("Uncaught exception (legacy hook)", exc_info=(exc_type, exc_value, exc_tb))
        try:
            with crash_path.open("a", encoding="utf-8") as fh:
                traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
        except Exception:  # pragma: no cover – best-effort
            pass

        # Delegate to modern crash reporter for ZIP generation
        from instant_scribe.crash_reporter import _handle_exception as _crash_hook  # type: ignore

        _crash_hook(exc_type, exc_value, exc_tb)

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
                        if hasattr(self.tray_app, "update_vram_badge"):
                            try:
                                self.tray_app.update_vram_badge(True)
                            except Exception:
                                pass
                        self._log.info("ASR model loaded into VRAM")
                    else:
                        self._log.error("Load model failed: %s", resp.payload)
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.error("Error loading model: %s", exc)

    # .................................................................
    def _toggle_pause(self) -> None:  # noqa: D401 – imperative API
        """Callback bound to *Ctrl+Alt+C* – pause/resume recording without ending session."""

        with self._lock:
            # Cannot pause if not currently in a *listening* session.
            if not self.is_listening:
                self._log.debug("Pause toggle ignored – not currently listening")
                return

            if self.is_paused:
                # Resume recording
                try:
                    self.audio_streamer.start()
                    self.is_paused = False
                    self.config.set("paused", False)
                    self.notification_manager.show_pause_state(False)
                    self._log.info("Recording resumed via user toggle")
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.error("Unable to resume recording: %s", exc)
            else:
                # Pause recording
                try:
                    self.audio_streamer.stop()
                    self.is_paused = True
                    self.config.set("paused", True)
                    self.notification_manager.show_pause_state(True)
                    self._log.info("Recording paused via user toggle")
                except Exception as exc:  # pylint: disable=broad-except
                    self._log.error("Unable to pause recording: %s", exc)

    # ------------------------------------------------------------------
    # Task 33 – GPU auto-unload helpers
    # ------------------------------------------------------------------

    @property
    def model_loaded(self) -> bool:  # noqa: D401 – read-only property
        """Return *True* when the ASR model is currently resident in VRAM."""
        return self._model_loaded

    def auto_unload_model(self) -> None:  # noqa: D401 – imperative API
        """Unload the ASR model triggered by **GPUResourceMonitor**.

        The logic mirrors :pyfunc:`_toggle_model_vram` but emits an explicit
        *auto* log entry and updates the tray badge.
        """

        with self._lock:
            if not self._model_loaded:
                return  # Already unloaded by user / previous auto event

            try:
                resp = self.worker.unload_model(timeout=30)
                if resp.ok:
                    self._model_loaded = False
                    # Reuse existing notification helper for consistency.
                    self.notification_manager.show_model_state("unloaded")
                    # Tray badge helper is *optional* (stubbed in unit-tests)
                    if hasattr(self.tray_app, "update_vram_badge"):
                        try:
                            self.tray_app.update_vram_badge(False)
                        except Exception:  # pragma: no cover – GUI failure
                            pass
                    self._log.warning("ASR model auto-unloaded to free VRAM")
                else:
                    self._log.error("Auto-unload model failed: %s", resp.payload)
            except Exception as exc:  # pylint: disable=broad-except
                self._log.error("Error during auto-unload: %s", exc)


# ---------------------------------------------------------------------------
# *console-script* entry-point
# ---------------------------------------------------------------------------

def main() -> None:  # noqa: D401 – script entry
    """Console entry‐point – parses minimal CLI flags then starts the app."""

    import argparse  # local import to avoid startup cost when imported as lib

    parser = argparse.ArgumentParser(description="Instant Scribe launcher")
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Force recovery prompt even if no incomplete session detected.",
    )
    parser.add_argument(
        "--stub-worker",
        action="store_true",
        help="Run with stub (CPU-only) transcription worker – useful for tests.",
    )

    args = parser.parse_args()

    orchestrator = ApplicationOrchestrator(
        use_stub_worker=args.stub_worker,
        auto_start=True,
        force_recover=args.recover,
    )

    # Block main thread until CTRL-C.  The tray UI / hotkey threads keep the
    # process alive.  In headless CI we exit immediately once *start()* has
    # completed so tests are not blocked.
    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:  # pragma: no cover – manual stop
        orchestrator.shutdown()


if __name__ == "__main__":  # pragma: no cover – manual execution helper
    main() 