"""Async Batch Transcription Pipeline - Task 52

This module provides an asyncio-based batch transcription system that can
process multiple audio chunks concurrently, improving throughput over the
traditional thread-based approach.

Key improvements:
- Asyncio-based concurrent processing
- Batch submission and processing
- Better resource utilization
- Configurable concurrency limits
- Integration with existing TranscriptionWorker
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from InstanceScrubber.transcription_worker import TranscriptionWorker, EngineResponse

__all__ = [
    "AsyncBatchTranscriber",
    "BatchRequest",
    "BatchResult",
]


@dataclass
class BatchRequest:
    """Represents a batch transcription request."""
    sequence_id: int
    audio_pcm: bytes
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BatchResult:
    """Represents a batch transcription result."""
    sequence_id: int
    text: str
    success: bool
    error: Optional[str] = None
    processing_time: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class AsyncBatchTranscriber:
    """Asyncio-based batch transcription system."""
    
    def __init__(
        self,
        *,
        max_concurrent_batches: int = 4,
        batch_size: int = 8,
        max_workers: Optional[int] = None,
        use_stub: bool = False,
        timeout_per_item: float = 30.0,
    ) -> None:
        """Initialize the async batch transcriber.
        
        Args:
            max_concurrent_batches: Maximum number of concurrent batch operations
            batch_size: Number of audio chunks to process in each batch
            max_workers: Number of worker threads for blocking operations
            use_stub: Whether to use stub transcription for testing
            timeout_per_item: Timeout per individual transcription item
        """
        self.max_concurrent_batches = max_concurrent_batches
        self.batch_size = batch_size
        self.timeout_per_item = timeout_per_item
        self._use_stub = use_stub
        
        # Async coordination
        self._semaphore = asyncio.Semaphore(max_concurrent_batches)
        self._pending_requests: List[BatchRequest] = []
        self._results: Dict[int, BatchResult] = {}
        self._sequence_counter = 0
        self._submitted_sequences: set[int] = set()
        
        # Worker management
        self._worker: Optional[TranscriptionWorker] = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers or 2)
        self._logger = logging.getLogger(__name__)
        
        # Performance tracking
        self._total_processed = 0
        self._total_processing_time = 0.0
        self._start_time = time.time()

    async def start(self) -> None:
        """Start the transcription worker."""
        if self._worker is None:
            self._worker = TranscriptionWorker(use_stub=self._use_stub)
            self._worker.start()
            self._logger.info("Async batch transcriber started")

    async def stop(self) -> None:
        """Stop the transcription worker and cleanup resources."""
        if self._worker:
            self._worker.stop(reason="async batch transcriber shutdown")
            self._worker = None
        
        self._executor.shutdown(wait=False)
        self._logger.info("Async batch transcriber stopped")

    async def submit_audio(self, audio_pcm: bytes, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Submit audio for batch transcription.
        
        Args:
            audio_pcm: Raw PCM audio data
            metadata: Optional metadata to associate with this request
            
        Returns:
            Sequence ID for tracking this request
        """
        sequence_id = self._sequence_counter
        self._sequence_counter += 1
        
        request = BatchRequest(
            sequence_id=sequence_id,
            audio_pcm=audio_pcm,
            timestamp=time.time(),
            metadata=metadata
        )
        
        self._pending_requests.append(request)
        self._submitted_sequences.add(sequence_id)
        self._logger.debug("Submitted audio chunk %d (%d bytes)", sequence_id, len(audio_pcm))
        
        # Trigger batch processing if we have enough items
        if len(self._pending_requests) >= self.batch_size:
            asyncio.create_task(self._process_batch())
        
        return sequence_id

    async def process_remaining(self) -> None:
        """Process any remaining pending requests."""
        if self._pending_requests:
            await self._process_batch()

    async def get_result(self, sequence_id: int, timeout: Optional[float] = None) -> BatchResult:
        """Get the result for a specific sequence ID.
        
        Args:
            sequence_id: The sequence ID to get results for
            timeout: Maximum time to wait for the result
            
        Returns:
            BatchResult for the specified sequence ID
            
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
            KeyError: If sequence ID is not found
        """
        start_time = time.time()
        
        while sequence_id not in self._results:
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Timeout waiting for result {sequence_id}")
            
            await asyncio.sleep(0.1)
        
        return self._results[sequence_id]

    async def get_all_results(self, timeout: Optional[float] = None) -> List[BatchResult]:
        """Get all results in sequence order.
        
        Args:
            timeout: Maximum time to wait for all results
            
        Returns:
            List of BatchResult objects in sequence order
        """
        # Wait for all pending requests to be processed
        await self.process_remaining()

        # Wait for all results to be available
        expected_count = len(self._submitted_sequences)

        start_time = time.time()
        while len(self._results) < expected_count:
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Timeout waiting for all results: got {len(self._results)}/{expected_count}")

            await asyncio.sleep(0.1)

        # Return results in sequence order
        return [self._results[i] for i in sorted(self._results.keys())]

    async def _process_batch(self) -> None:
        """Process a batch of pending requests."""
        if not self._pending_requests:
            return
        
        # Extract batch to process
        batch_requests = self._pending_requests[:self.batch_size]
        self._pending_requests = self._pending_requests[self.batch_size:]
        
        async with self._semaphore:
            await self._process_batch_concurrent(batch_requests)

    async def _process_batch_concurrent(self, requests: List[BatchRequest]) -> None:
        """Process a batch of requests concurrently."""
        if not self._worker:
            raise RuntimeError("Worker not started")
        
        self._logger.debug("Processing batch of %d requests", len(requests))
        
        # Create tasks for concurrent processing
        tasks = [
            self._process_single_request(request)
            for request in requests
        ]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Store results
        for request, result in zip(requests, results):
            if isinstance(result, Exception):
                batch_result = BatchResult(
                    sequence_id=request.sequence_id,
                    text="",
                    success=False,
                    error=str(result),
                    metadata=request.metadata
                )
            else:
                batch_result = result
            
            self._results[request.sequence_id] = batch_result
            self._total_processed += 1

    async def _process_single_request(self, request: BatchRequest) -> BatchResult:
        """Process a single transcription request."""
        start_time = time.time()
        
        try:
            # Run the blocking transcription in the thread pool
            loop = asyncio.get_event_loop()
            response: EngineResponse = await loop.run_in_executor(
                self._executor,
                lambda: self._worker.transcribe(request.audio_pcm, timeout=self.timeout_per_item)
            )
            
            processing_time = time.time() - start_time
            self._total_processing_time += processing_time
            
            if response.ok:
                return BatchResult(
                    sequence_id=request.sequence_id,
                    text=str(response.payload),
                    success=True,
                    processing_time=processing_time,
                    metadata=request.metadata
                )
            else:
                return BatchResult(
                    sequence_id=request.sequence_id,
                    text="",
                    success=False,
                    error=str(response.payload),
                    processing_time=processing_time,
                    metadata=request.metadata
                )
        
        except Exception as exc:
            processing_time = time.time() - start_time
            self._logger.exception("Failed to process request %d", request.sequence_id)
            
            return BatchResult(
                sequence_id=request.sequence_id,
                text="",
                success=False,
                error=str(exc),
                processing_time=processing_time,
                metadata=request.metadata
            )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        elapsed_time = time.time() - self._start_time
        
        return {
            "total_processed": self._total_processed,
            "total_processing_time": self._total_processing_time,
            "elapsed_time": elapsed_time,
            "average_processing_time": (
                self._total_processing_time / self._total_processed
                if self._total_processed > 0 else 0.0
            ),
            "throughput_items_per_second": (
                self._total_processed / elapsed_time
                if elapsed_time > 0 else 0.0
            ),
            "pending_requests": len(self._pending_requests),
            "completed_results": len(self._results),
        }

    # Context manager support
    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
