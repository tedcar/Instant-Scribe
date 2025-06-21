from __future__ import annotations

"""Background *batch transcription* helper – fulfils **DEV_TASKS.md – Task 21**.

The *BatchTranscriber* consumes long-running recordings in **fixed-length time
windows** (10-minute default) *while* the recording is still in progress.  Each
window is transcribed in parallel so that the *final* stop-and-merge step can
return an aggregated result almost instantly (< 3 s for a 30-minute dummy
recording as asserted by the integration test).

Design highlights
-----------------
1. A lightweight **thread-pool** executes the blocking ``TranscriptionWorker``
   calls concurrently.  Threading is sufficient because the heavy lifting
   happens in a *separate* process (CUDA kernels) or – in CI – the fast stub
   model.  Therefore the GIL is *not* a bottleneck.
2. Every submitted slice receives a **monotonically increasing sequence
   number** so that ``finalise()`` can stitch the partial transcripts back
   together in the correct chronological order.
3. The helper is completely **self-contained** and can be used standalone in
   tests or integrated into the real application orchestrator at a later
   stage.
"""

from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Optional
import logging

from InstanceScrubber.transcription_worker import TranscriptionWorker, EngineResponse

__all__ = [
    "BatchTranscriber",
]


class BatchTranscriber:  # pylint: disable=too-few-public-methods
    """High-level API for background batch transcription."""

    def __init__(
        self,
        *,
        batch_length_ms: int = 600_000,
        overlap_ms: int = 0,
        max_workers: Optional[int] = None,
        use_stub: bool = False,
    ) -> None:
        self.batch_length_ms = batch_length_ms
        self.overlap_ms = overlap_ms
        self._seq: int = 0
        self._futures: Dict[int, Future[EngineResponse]] = {}

        # The *TranscriptionWorker* already isolates the heavy model in a
        # separate *process* when *use_stub=False*.  In CI we pass
        # ``use_stub=True`` for fast, dependency-free execution.
        self._worker = TranscriptionWorker(use_stub=use_stub)
        self._worker.start()

        # Thread-pool off-loads the blocking *transcribe()* calls so multiple
        # 10-minute windows can be processed concurrently.
        self._executor = ThreadPoolExecutor(max_workers=max_workers or 4)

    # ------------------------------------------------------------------
    # Slice submission helpers
    # ------------------------------------------------------------------
    def submit_slice(self, audio_pcm: bytes) -> None:  # noqa: D401 – imperative API
        """Schedule *audio_pcm* for transcription.

        The caller is responsible for slicing the *recording* into fixed-length
        windows (see *AudioListener* + *AudioSpooler* logic).  Here we simply
        forward the PCM bytes to the underlying *TranscriptionWorker*.
        """
        seq = self._seq
        self._seq += 1

        logging.debug("Submitting batch slice seq=%d (%d bytes)", seq, len(audio_pcm))
        fut = self._executor.submit(self._worker.transcribe, audio_pcm)
        self._futures[seq] = fut

    # ------------------------------------------------------------------
    # Finalisation helpers
    # ------------------------------------------------------------------
    def finalise(self, *, timeout_per_slice: float | None = 30) -> str:  # noqa: D401 – imperative API
        """Wait for *all* slices to complete and return the concatenated text."""
        logging.info("Finalising batch transcription – awaiting %d partial results", len(self._futures))
        ordered_text: List[str] = []
        for seq in sorted(self._futures):
            fut = self._futures[seq]
            resp = fut.result(timeout=timeout_per_slice)
            if not resp.ok:
                raise RuntimeError(f"Batch slice {seq} failed: {resp.payload}")
            ordered_text.append(str(resp.payload))

        # Join with a single space – the model already returns punctuation.
        return " ".join(ordered_text)

    # ------------------------------------------------------------------
    # Clean-up helpers
    # ------------------------------------------------------------------
    def close(self) -> None:  # noqa: D401 – imperative API
        """Shut down the underlying worker & executor."""
        logging.debug("Shutting down BatchTranscriber")
        self._executor.shutdown(wait=False, cancel_futures=False)
        self._worker.stop(reason="batch transcriber close")

    # ------------------------------------------------------------------
    # Context manager sugar
    # ------------------------------------------------------------------
    def __enter__(self):  # noqa: D401 – context manager helper
        return self

    def __exit__(self, exc_type, exc_value, traceback):  # noqa: D401 – context manager helper
        self.close()
        # Do *not* swallow exceptions.
        return False 