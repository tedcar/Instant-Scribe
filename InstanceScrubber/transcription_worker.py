from __future__ import annotations

"""ASR transcription worker powered by NVIDIA Parakeet & NeMo.

This module fulfils *DEV_TASKS.md – Task 6* requirements:

6.1 ``TranscriptionEngine.load_model()`` loads the Parakeet model once and
    keeps it resident in VRAM.
6.2 ``get_plain_transcription`` / ``get_detailed_transcription`` provide the
    two public inference APIs.
6.3 A light warm-up run is executed on load to reduce first-call latency.
6.4 CUDA OOM and other inference failures are caught and returned as a
    structured *error* response to the caller (used by the worker loop).
6.5 ``benchmark_rtf`` computes the *Real-Time-Factor* (RTFx) for any given
    audio array to ensure performance stays within the < 2 s target.

The heavy NeMo dependency is imported lazily so that unit-tests can run in
CI environments without the GPU toolchain or large model files.  When NeMo is
unavailable *or* the caller explicitly requests a stub via ``use_stub=True``
the engine falls back to a lightweight fake model that returns deterministic
outputs.  This makes the public API fully testable without network access.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple

import numpy as np
from InstanceScrubber.audio_processing import preprocess_audio  # <-- NEW IMPORT
from InstanceScrubber.config_manager import ConfigManager as _CM  # <-- NEW IMPORT

# ---------------------------------------------------------------------------
# Internal helpers – optional NeMo import with graceful fallback
# ---------------------------------------------------------------------------

try:
    import importlib
    nemo_asr = importlib.import_module("nemo.collections.asr")  # type: ignore
except Exception:  # noqa: BLE001 – broad except on purpose; we fall back to stub

    class _StubHypothesis:  # pylint: disable=too-few-public-methods
        """Very small stand-in replicating the bits of NeMo's Hypothesis API"""

        def __init__(self, text: str):
            self.text = text
            self.timestamp = {"word": []}

    class _StubASRModel:  # pylint: disable=too-few-public-methods
        """Fake ASR model exposing a *transcribe()* method matching NeMo."""

        def transcribe(  # noqa: D401 – signature mirrors real API
            self,
            *,
            audio: Sequence[np.ndarray] | None = None,
            batch_size: int = 1,
            timestamps: bool | None = None,
            **_kwargs,
        ) -> List[Any]:
            """Return fixed results so tests are deterministic."""
            if timestamps:
                return [_StubHypothesis("hello world (detailed)") for _ in audio]  # type: ignore[arg-type]
            return ["hello world" for _ in audio]  # type: ignore[arg-type]

    nemo_asr = None  # type: ignore

# ---------------------------------------------------------------------------
# Public classes
# ---------------------------------------------------------------------------


class TranscriptionEngine:  # pylint: disable=too-many-public-methods
    """Thin OO wrapper around a NeMo ASR model (Parakeet)."""

    _DEFAULT_MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v2"

    def __init__(self) -> None:
        self.model: Any | None = None

    # ------------------------------------------------------------------
    # Model lifecycle helpers
    # ------------------------------------------------------------------

    def load_model(self, *, use_stub: bool = False) -> None:
        """Load the Parakeet model into GPU/CPU memory.

        The heavy import is done lazily so unit-tests can opt-out by passing
        ``use_stub=True`` which forces a dummy implementation that returns
        deterministic outputs without external dependencies.
        """

        if use_stub or nemo_asr is None:
            logging.info("Using stub ASR model – real NeMo not available or skipped")
            # pylint: disable=protected-access
            self.model = _StubASRModel()  # type: ignore[name-defined]
            return

        try:
            logging.info("Loading Parakeet model – this can take a while on first run …")
            self.model = nemo_asr.models.ASRModel.from_pretrained(  # type: ignore[attr-defined]
                model_name=self._DEFAULT_MODEL_NAME,
            )
            logging.info("Model loaded – performing warm-up inference")
            self._warm_up()
        except Exception as exc:  # pragma: no cover – safety
            logging.critical("Failed to load Parakeet model: %s", exc)
            self.model = None
            raise

    def _warm_up(self) -> None:
        """Run a short inference pass to pay the JIT & CUDA launch costs up-front."""
        if self.model is None:
            return
        silence = np.zeros(8000, dtype=np.int16)  # 0.5 s of silence @ 16 kHz
        try:
            _ = self.model.transcribe(audio=[silence], batch_size=1)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover – warm-up failures non-fatal
            logging.warning("Warm-up inference failed: %s", exc)

    def unload_model(self) -> None:  # noqa: D401 – imperative API
        """Free GPU/CPU memory by discarding the loaded model.

        When running on a CUDA-capable system we explicitly call
        ``torch.cuda.empty_cache()`` after deleting the model reference so
        that VRAM is returned immediately.  The call is wrapped in a *try*
        block so the method becomes a no-op on systems without PyTorch / GPU
        support (stub mode, CI, etc.).
        """

        if self.model is None:
            return  # Already unloaded – idempotent

        # Drop the strong reference first so Python can reclaim memory.
        _tmp = self.model
        self.model = None
        del _tmp  # noqa: PLW0127 – explicit cleanup for clarity

        # If torch is available attempt to clear the CUDA allocator cache.
        try:
            import torch  # pylint: disable=import-error,import-outside-toplevel

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # pragma: no cover – soft-fail in stub/CPU env
            pass

    # ------------------------------------------------------------------
    # Public inference APIs
    # ------------------------------------------------------------------

    def get_plain_transcription(self, audio: np.ndarray) -> str:
        """Return best-guess transcript as a plain string."""
        self._ensure_model_loaded()
        try:
            preds = self.model.transcribe(audio=[audio], batch_size=1)  # type: ignore[attr-defined]
            return preds[0] if preds else ""
        except RuntimeError as exc:
            # Intercept CUDA OOM and similar issues – surface as regular Exception
            if "CUDA out of memory" in str(exc):
                raise TranscriptionError("cuda_oom", "CUDA out of memory during inference")
            raise

    def get_detailed_transcription(self, audio: np.ndarray) -> Tuple[str, Any]:
        """Return transcript plus word-level timestamps (if supported)."""
        self._ensure_model_loaded()
        preds = self.model.transcribe(  # type: ignore[attr-defined]
            audio=[audio], batch_size=1, timestamps=True
        )
        if not preds:
            return "", []
        first = preds[0]
        # Real NeMo returns a Hypothesis object; our stub mimics with .text attr
        text = getattr(first, "text", str(first))
        word_ts = getattr(first, "timestamp", {}).get("word", [])
        return text, word_ts

    # ------------------------------------------------------------------
    # Bench-marking helper
    # ------------------------------------------------------------------

    def benchmark_rtf(self, audio: np.ndarray) -> float:
        """Return *Real-Time Factor* (RTFx).  > 1 => faster than real-time."""
        start = time.perf_counter()
        _ = self.get_plain_transcription(audio)
        duration = time.perf_counter() - start
        audio_secs = len(audio) / 16_000  # hard-coded 16 kHz sample rate
        if duration == 0:
            return float("inf")
        return audio_secs / duration

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _ensure_model_loaded(self) -> None:
        if self.model is None:
            raise RuntimeError("ASR model not loaded – call load_model() first")


@dataclass(slots=True)
class EngineResponse:
    """Structured result returned by the worker IPC layer."""

    ok: bool
    """True on success; False when an error occurred."""

    payload: Any
    """Either the transcription text or an *error* dict."""


class TranscriptionError(Exception):  # pylint: disable=too-few-public-methods
    """Custom exception type for predictable error handling by callers."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Worker process loop
# ---------------------------------------------------------------------------

import multiprocessing as _mp
from ipc.messages import Shutdown, Transcribe, Response, UnloadModel, LoadModel  # noqa: E402 – avoid circular at top
from ipc.queue_wrapper import IPCQueue  # noqa: E402


def _worker_process(request_q: _mp.Queue, response_q: _mp.Queue, *, use_stub: bool = False):
    """Entry-point executed in the background *spawned* process."""

    # ------------------------------------------------------------------
    # Load configuration once on process start so that toggles can be
    # adjusted by the main application at runtime through a simple config
    # file reload without code changes.
    # ------------------------------------------------------------------

    _cfg = _CM()
    _enable_agc = bool(_cfg.get("enable_agc", False))
    _enable_ns = bool(_cfg.get("enable_noise_suppression", False))

    engine = TranscriptionEngine()
    try:
        engine.load_model(use_stub=use_stub)
    except Exception as exc:  # pragma: no cover – propagate fatal load failure
        logging.critical("Transcription worker failed to start: %s", exc)
        response_q.put(Response(result=EngineResponse(ok=False, payload={"error": str(exc)})))
        return

    while True:
        msg = request_q.get()  # blocking – the main app owns the timeout
        if isinstance(msg, Shutdown):
            logging.info("Transcription worker shutting down (%s)", msg.reason)
            break
        if isinstance(msg, Transcribe):
            try:
                # ------------------------------------------------------
                # Optional AGC & noise-suppression (Task 37)
                # ------------------------------------------------------
                processed = preprocess_audio(
                    msg.audio,
                    enable_agc=_enable_agc,
                    enable_noise_suppression=_enable_ns,
                )

                # Convert raw 16-bit PCM bytes → NumPy array for the engine
                audio_np = np.frombuffer(processed, dtype=np.int16)
                text = engine.get_plain_transcription(audio_np)
                response_q.put(Response(result=EngineResponse(ok=True, payload=text)))
            except Exception as exc:  # pylint: disable=broad-except – robustness
                logging.exception("Transcription failed: %s", exc)
                response_q.put(
                    Response(result=EngineResponse(ok=False, payload={"error": str(exc)}))
                )
        elif isinstance(msg, UnloadModel):
            try:
                engine.unload_model()
                response_q.put(
                    Response(result=EngineResponse(ok=True, payload={"state": "unloaded"}))
                )
            except Exception as exc:  # pragma: no cover – unexpected
                logging.exception("Unload model failed: %s", exc)
                response_q.put(
                    Response(result=EngineResponse(ok=False, payload={"error": str(exc)}))
                )
        elif isinstance(msg, LoadModel):
            try:
                engine.load_model(use_stub=use_stub)
                response_q.put(
                    Response(result=EngineResponse(ok=True, payload={"state": "loaded"}))
                )
            except Exception as exc:  # pragma: no cover
                logging.exception("Load model failed: %s", exc)
                response_q.put(
                    Response(result=EngineResponse(ok=False, payload={"error": str(exc)}))
                )


class TranscriptionWorker:
    """Facade managing the background worker process."""

    def __init__(self, *, use_stub: bool = False):
        self._use_stub = use_stub

        # *Optimization for test environments*: when running in *stub* mode we
        # avoid the expensive Windows **multiprocessing spawn** overhead by
        # executing the `TranscriptionEngine` directly inside the parent
        # process.  This keeps unit-tests snappy and eliminates flaky
        # timeouts when the CI runner is under heavy load.
        if use_stub:
            self._inline_engine = TranscriptionEngine()
            self._inline_engine.load_model(use_stub=True)
            self._proc = None  # type: ignore[assignment]
            self._requests = None  # type: ignore[assignment]
            self._responses = None  # type: ignore[assignment]
        else:
            self._inline_engine = None  # type: ignore[attr-defined]
            self._requests: IPCQueue[Any] = IPCQueue()
            self._responses: IPCQueue[Any] = IPCQueue()
            self._proc: _mp.Process | None = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise the worker – spawn a *separate* process unless we are
        running in the fast *inline stub* mode used by unit-tests."""

        if self._use_stub:
            # Inline mode – nothing to spawn.
            return

        if self._proc and self._proc.is_alive():
            logging.debug("Worker already running – start() ignored")
            return

        ctx = _mp.get_context("spawn")
        self._proc = ctx.Process(
            target=_worker_process,
            args=(self._requests.raw, self._responses.raw),
            kwargs={"use_stub": False},
        )
        self._proc.start()
        logging.info("Transcription worker process started (pid=%d)", self._proc.pid)

    def stop(self, *, reason: str = "normal shutdown") -> None:
        """Terminate the worker process gracefully (no-op for inline stub)."""

        if self._use_stub:
            # Free model memory to simulate *unload* on shutdown.
            if self._inline_engine:
                self._inline_engine.unload_model()
            return

        if not self._proc:
            return
        self._requests.put(Shutdown(reason=reason))
        self._proc.join(timeout=10)
        if self._proc.is_alive():
            self._proc.kill()
        self._proc = None
        logging.info("Transcription worker stopped")

    def transcribe(self, audio_pcm: bytes, *, timeout: float | None = 30) -> EngineResponse:
        """Synchronous convenience wrapper – transcribe audio and return result.

        In *inline stub* mode we bypass IPC entirely for speed; otherwise the
        call is proxied to the background worker process via the request
        queue and blocks until a response is received or *timeout* expires.
        """

        if self._use_stub:
            assert self._inline_engine is not None  # for type checker
            try:
                # Apply same preprocessing logic as the background worker so
                # that unit-tests exercise the full Task-37 pipeline even in
                # fast *inline* mode.
                cfg = _CM()
                processed_pcm = preprocess_audio(
                    audio_pcm,
                    enable_agc=bool(cfg.get("enable_agc", False)),
                    enable_noise_suppression=bool(cfg.get("enable_noise_suppression", False)),
                )

                audio_np = np.frombuffer(processed_pcm, dtype=np.int16)
                text = self._inline_engine.get_plain_transcription(audio_np)
                return EngineResponse(ok=True, payload=text)
            except Exception as exc:  # pragma: no cover – stub path safety
                return EngineResponse(ok=False, payload={"error": str(exc)})

        self._requests.put(Transcribe(audio=audio_pcm))
        resp: Response[EngineResponse] = self._responses.get(timeout=timeout)
        return resp.result

    # ------------------------------------------------------------------
    # VRAM toggle helpers (Task 11)
    # ------------------------------------------------------------------

    def unload_model(self, *, timeout: float | None = 30) -> EngineResponse:
        """Unload the ASR model (inline stub or background worker)."""

        if self._use_stub:
            assert self._inline_engine is not None
            try:
                self._inline_engine.unload_model()
                return EngineResponse(ok=True, payload={"state": "unloaded"})
            except Exception as exc:  # pragma: no cover
                return EngineResponse(ok=False, payload={"error": str(exc)})

        from ipc.messages import UnloadModel  # local import avoids circularity

        self._requests.put(UnloadModel())
        resp: Response[EngineResponse] = self._responses.get(timeout=timeout)
        return resp.result

    def load_model(self, *, timeout: float | None = 120) -> EngineResponse:
        """Reload the ASR model after *unload* (inline stub or background worker)."""

        if self._use_stub:
            assert self._inline_engine is not None
            try:
                self._inline_engine.load_model(use_stub=True)
                return EngineResponse(ok=True, payload={"state": "loaded"})
            except Exception as exc:  # pragma: no cover
                return EngineResponse(ok=False, payload={"error": str(exc)})

        from ipc.messages import LoadModel  # local import avoids circularity

        self._requests.put(LoadModel())
        resp: Response[EngineResponse] = self._responses.get(timeout=timeout)
        return resp.result

    # ------------------------------------------------------------------
    # Context-manager helpers
    # ------------------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: D401 – context manager boilerplate
        self.stop(reason="context manager exit")
        return False


__all__ = [
    "TranscriptionEngine",
    "TranscriptionWorker",
    "EngineResponse",
    "TranscriptionError",
] 