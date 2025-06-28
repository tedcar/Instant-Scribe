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
import asyncio
import time

from InstanceScrubber.transcription_worker import TranscriptionWorker, EngineResponse

__all__ = [
    "BatchTranscriber",
    "AsyncBatchTranscriber",  # Task 52 – async version
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


# Task 52 – Async Batch Transcription Implementation
class AsyncBatchTranscriber:
    """Asyncio-based batch transcriber for improved concurrent processing."""

    def __init__(
        self,
        *,
        batch_length_ms: int = 600_000,
        overlap_ms: int = 0,
        max_concurrent: int = 8,
        use_stub: bool = False,
    ) -> None:
        """Initialize async batch transcriber.

        Args:
            batch_length_ms: Length of each batch in milliseconds
            overlap_ms: Overlap between batches in milliseconds
            max_concurrent: Maximum concurrent transcription operations
            use_stub: Whether to use stub transcription for testing
        """
        self.batch_length_ms = batch_length_ms
        self.overlap_ms = overlap_ms
        self.max_concurrent = max_concurrent
        self._use_stub = use_stub

        self._seq: int = 0
        self._pending_tasks: Dict[int, asyncio.Task] = {}
        self._results: Dict[int, EngineResponse] = {}
        self._worker: Optional[TranscriptionWorker] = None
        self._semaphore: Optional[asyncio.Semaphore] = None

        # Performance tracking
        self._start_time = time.time()
        self._total_processed = 0
        self._total_processing_time = 0.0

    async def start(self) -> None:
        """Start the async transcription worker."""
        if self._worker is None:
            self._worker = TranscriptionWorker(use_stub=self._use_stub)
            self._worker.start()
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
            logging.info("Async batch transcriber started with max_concurrent=%d", self.max_concurrent)

    async def stop(self) -> None:
        """Stop the transcription worker and cancel pending tasks."""
        # Cancel all pending tasks
        for task in self._pending_tasks.values():
            if not task.done():
                task.cancel()

        # Wait for tasks to complete or be cancelled
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks.values(), return_exceptions=True)

        # Stop the worker
        if self._worker:
            self._worker.stop(reason="async batch transcriber shutdown")
            self._worker = None

        logging.info("Async batch transcriber stopped")

    async def submit_slice_async(self, audio_pcm: bytes) -> int:
        """Submit audio slice for async transcription.

        Args:
            audio_pcm: Raw PCM audio data

        Returns:
            Sequence number for tracking this slice
        """
        if not self._worker or not self._semaphore:
            raise RuntimeError("AsyncBatchTranscriber not started")

        seq = self._seq
        self._seq += 1

        # Create async task for this slice
        task = asyncio.create_task(self._transcribe_slice_async(seq, audio_pcm))
        self._pending_tasks[seq] = task

        logging.debug("Submitted async batch slice seq=%d (%d bytes)", seq, len(audio_pcm))
        return seq

    async def _transcribe_slice_async(self, seq: int, audio_pcm: bytes) -> EngineResponse:
        """Transcribe a single slice asynchronously."""
        async with self._semaphore:
            start_time = time.time()

            try:
                # Run the blocking transcription in a thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,  # Use default thread pool
                    lambda: self._worker.transcribe(audio_pcm, timeout=30.0)
                )

                processing_time = time.time() - start_time
                self._total_processing_time += processing_time
                self._total_processed += 1

                self._results[seq] = response
                logging.debug("Async slice %d completed in %.2fs", seq, processing_time)

                return response

            except Exception as exc:
                processing_time = time.time() - start_time
                self._total_processing_time += processing_time

                error_response = EngineResponse(ok=False, payload={"error": str(exc)})
                self._results[seq] = error_response
                logging.error("Async slice %d failed in %.2fs: %s", seq, processing_time, exc)

                return error_response

            finally:
                # Clean up the task reference
                self._pending_tasks.pop(seq, None)

    async def finalise_async(self, timeout: Optional[float] = None) -> str:
        """Wait for all slices to complete and return concatenated text.

        Args:
            timeout: Maximum time to wait for all slices to complete

        Returns:
            Concatenated transcription text
        """
        logging.info("Finalising async batch transcription – awaiting %d slices", len(self._pending_tasks))

        # Wait for all pending tasks
        if self._pending_tasks:
            try:
                if timeout:
                    await asyncio.wait_for(
                        asyncio.gather(*self._pending_tasks.values(), return_exceptions=True),
                        timeout=timeout
                    )
                else:
                    await asyncio.gather(*self._pending_tasks.values(), return_exceptions=True)
            except asyncio.TimeoutError:
                logging.warning("Async batch finalisation timed out")
                # Cancel remaining tasks
                for task in self._pending_tasks.values():
                    if not task.done():
                        task.cancel()

        # Collect results in order
        ordered_text: List[str] = []
        for seq in sorted(self._results.keys()):
            resp = self._results[seq]
            if resp.ok:
                ordered_text.append(str(resp.payload))
            else:
                logging.warning("Slice %d failed: %s", seq, resp.payload)
                # Continue with empty string for failed slices
                ordered_text.append("")

        return " ".join(text for text in ordered_text if text)

    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics for benchmarking."""
        elapsed_time = time.time() - self._start_time

        return {
            "total_processed": self._total_processed,
            "total_processing_time": self._total_processing_time,
            "elapsed_time": elapsed_time,
            "average_processing_time": (
                self._total_processing_time / self._total_processed
                if self._total_processed > 0 else 0.0
            ),
            "throughput_slices_per_second": (
                self._total_processed / elapsed_time
                if elapsed_time > 0 else 0.0
            ),
            "pending_tasks": len(self._pending_tasks),
            "completed_results": len(self._results),
        }

    # Async context manager support
    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
        # Do *not* swallow exceptions.
        return False 