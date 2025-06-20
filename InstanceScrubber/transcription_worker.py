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
from ipc.messages import Shutdown, Transcribe, Response  # noqa: E402 – avoid circular at top
from ipc.queue_wrapper import IPCQueue  # noqa: E402


def _worker_process(request_q: _mp.Queue, response_q: _mp.Queue, *, use_stub: bool = False):
    """Entry-point executed in the background *spawned* process."""

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
                # Convert raw 16-bit PCM bytes → NumPy array for the engine
                audio_np = np.frombuffer(msg.audio, dtype=np.int16)
                text = engine.get_plain_transcription(audio_np)
                response_q.put(Response(result=EngineResponse(ok=True, payload=text)))
            except Exception as exc:  # pylint: disable=broad-except – robustness
                logging.exception("Transcription failed: %s", exc)
                response_q.put(
                    Response(result=EngineResponse(ok=False, payload={"error": str(exc)}))
                )


class TranscriptionWorker:
    """Facade managing the background worker process."""

    def __init__(self, *, use_stub: bool = False):
        self._requests: IPCQueue[Any] = IPCQueue()
        self._responses: IPCQueue[Any] = IPCQueue()
        self._proc: _mp.Process | None = None
        self._use_stub = use_stub

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn the worker process if not already running."""
        if self._proc and self._proc.is_alive():
            logging.debug("Worker already running – start() ignored")
            return
        ctx = _mp.get_context("spawn")
        self._proc = ctx.Process(
            target=_worker_process,
            args=(self._requests.raw, self._responses.raw),
            kwargs={"use_stub": self._use_stub},
        )
        self._proc.start()
        logging.info("Transcription worker process started (pid=%d)", self._proc.pid)

    def stop(self, *, reason: str = "normal shutdown") -> None:
        """Terminate the worker process gracefully."""
        if not self._proc:
            return
        self._requests.put(Shutdown(reason=reason))
        self._proc.join(timeout=10)
        if self._proc.is_alive():
            self._proc.kill()
        self._proc = None
        logging.info("Transcription worker stopped")

    def transcribe(self, audio_pcm: bytes, *, timeout: float | None = 30) -> EngineResponse:
        """Synchronous convenience wrapper – send audio and wait for result."""
        self._requests.put(Transcribe(audio=audio_pcm))
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