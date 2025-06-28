"""Tests for Task 52: Concurrent Batch Transcription Pipeline

Tests both async batch transcription (52.1) and throughput benchmarking (52.2).
"""

from __future__ import annotations

import asyncio
import pytest
import time
from unittest.mock import patch, MagicMock

from InstanceScrubber.batch_transcriber import AsyncBatchTranscriber
from InstanceScrubber.async_batch_transcriber import AsyncBatchTranscriber as StandaloneAsyncBatchTranscriber
from InstanceScrubber.transcription_worker import EngineResponse


class TestAsyncBatchTranscriber:
    """Test the async batch transcriber functionality."""

    @pytest.fixture
    def dummy_audio_chunks(self):
        """Generate dummy audio chunks for testing."""
        # Create 5 chunks of dummy audio data
        chunks = []
        for i in range(5):
            chunk = bytes([i] * 1000)  # 1000 bytes per chunk
            chunks.append(chunk)
        return chunks

    @pytest.mark.asyncio
    async def test_async_batch_transcriber_basic(self, dummy_audio_chunks):
        """Test basic async batch transcriber functionality."""
        async with AsyncBatchTranscriber(use_stub=True, max_concurrent=4) as abt:
            # Submit all chunks
            sequence_ids = []
            for chunk in dummy_audio_chunks:
                seq_id = await abt.submit_slice_async(chunk)
                sequence_ids.append(seq_id)
            
            # Verify sequence IDs are sequential
            assert sequence_ids == list(range(len(dummy_audio_chunks)))
            
            # Finalize and get results
            result_text = await abt.finalise_async(timeout=30)
            
            # With stub transcriber, each chunk should return "hello world"
            expected_text = " ".join(["hello world"] * len(dummy_audio_chunks))
            assert result_text == expected_text

    @pytest.mark.asyncio
    async def test_async_batch_transcriber_performance_stats(self, dummy_audio_chunks):
        """Test that performance statistics are tracked correctly."""
        async with AsyncBatchTranscriber(use_stub=True, max_concurrent=4) as abt:
            # Submit chunks
            for chunk in dummy_audio_chunks:
                await abt.submit_slice_async(chunk)
            
            # Finalize
            await abt.finalise_async(timeout=30)
            
            # Check performance stats
            stats = abt.get_performance_stats()
            
            assert stats["total_processed"] == len(dummy_audio_chunks)
            assert stats["completed_results"] == len(dummy_audio_chunks)
            assert stats["pending_tasks"] == 0
            assert stats["throughput_slices_per_second"] > 0
            assert stats["average_processing_time"] >= 0

    @pytest.mark.asyncio
    async def test_async_batch_transcriber_concurrent_processing(self, dummy_audio_chunks):
        """Test that concurrent processing improves performance."""
        # Test with low concurrency
        start_time = time.time()
        async with AsyncBatchTranscriber(use_stub=True, max_concurrent=1) as abt:
            for chunk in dummy_audio_chunks:
                await abt.submit_slice_async(chunk)
            await abt.finalise_async(timeout=30)
        low_concurrency_time = time.time() - start_time
        
        # Test with high concurrency
        start_time = time.time()
        async with AsyncBatchTranscriber(use_stub=True, max_concurrent=8) as abt:
            for chunk in dummy_audio_chunks:
                await abt.submit_slice_async(chunk)
            await abt.finalise_async(timeout=30)
        high_concurrency_time = time.time() - start_time
        
        # High concurrency should be faster (or at least not significantly slower)
        # Allow some tolerance for test environment variations
        assert high_concurrency_time <= low_concurrency_time * 1.5

    @pytest.mark.asyncio
    async def test_async_batch_transcriber_error_handling(self):
        """Test error handling in async batch transcriber."""
        async with AsyncBatchTranscriber(use_stub=True, max_concurrent=4) as abt:
            # Mock the worker to return an error
            with patch.object(abt._worker, 'transcribe') as mock_transcribe:
                mock_transcribe.return_value = EngineResponse(ok=False, payload={"error": "Test error"})
                
                # Submit a chunk
                seq_id = await abt.submit_slice_async(b"test audio")
                
                # Finalize should handle the error gracefully
                result_text = await abt.finalise_async(timeout=30)
                
                # Should return empty string for failed transcription
                assert result_text == ""

    @pytest.mark.asyncio
    async def test_async_batch_transcriber_timeout_handling(self, dummy_audio_chunks):
        """Test timeout handling in async batch transcriber."""
        async with AsyncBatchTranscriber(use_stub=True, max_concurrent=4) as abt:
            # Submit chunks
            for chunk in dummy_audio_chunks:
                await abt.submit_slice_async(chunk)
            
            # Test with very short timeout
            with pytest.raises(asyncio.TimeoutError):
                await abt.finalise_async(timeout=0.001)


class TestStandaloneAsyncBatchTranscriber:
    """Test the standalone async batch transcriber."""

    @pytest.fixture
    def dummy_audio_chunks(self):
        """Generate dummy audio chunks for testing."""
        chunks = []
        for i in range(8):  # Use 8 chunks to test batching
            chunk = bytes([i] * 500)
            chunks.append(chunk)
        return chunks

    @pytest.mark.asyncio
    async def test_standalone_async_batch_transcriber_basic(self, dummy_audio_chunks):
        """Test basic standalone async batch transcriber functionality."""
        async with StandaloneAsyncBatchTranscriber(
            use_stub=True,
            max_concurrent_batches=2,
            batch_size=4
        ) as sabt:
            # Submit all chunks
            sequence_ids = []
            for chunk in dummy_audio_chunks:
                seq_id = await sabt.submit_audio(chunk)
                sequence_ids.append(seq_id)
            
            # Get all results
            results = await sabt.get_all_results(timeout=30)
            
            # Verify we got results for all chunks
            assert len(results) == len(dummy_audio_chunks)
            
            # Verify all results are successful
            assert all(result.success for result in results)
            
            # Verify sequence order
            assert [result.sequence_id for result in results] == sequence_ids

    @pytest.mark.asyncio
    async def test_standalone_async_batch_transcriber_batching(self, dummy_audio_chunks):
        """Test that batching works correctly."""
        async with StandaloneAsyncBatchTranscriber(
            use_stub=True,
            max_concurrent_batches=2,
            batch_size=3  # Smaller batch size to test batching
        ) as sabt:
            # Submit chunks
            for chunk in dummy_audio_chunks:
                await sabt.submit_audio(chunk)
            
            # Process remaining chunks
            await sabt.process_remaining()
            
            # Get performance stats
            stats = sabt.get_performance_stats()
            
            assert stats["total_processed"] == len(dummy_audio_chunks)
            assert stats["completed_results"] == len(dummy_audio_chunks)

    @pytest.mark.asyncio
    async def test_standalone_async_batch_transcriber_individual_results(self, dummy_audio_chunks):
        """Test getting individual results by sequence ID."""
        async with StandaloneAsyncBatchTranscriber(
            use_stub=True,
            max_concurrent_batches=2,
            batch_size=4
        ) as sabt:
            # Submit first chunk
            seq_id = await sabt.submit_audio(dummy_audio_chunks[0])
            
            # Get result for specific sequence ID
            result = await sabt.get_result(seq_id, timeout=30)
            
            assert result.sequence_id == seq_id
            assert result.success is True
            assert result.text == "hello world"

    @pytest.mark.asyncio
    async def test_standalone_async_batch_transcriber_metadata(self, dummy_audio_chunks):
        """Test metadata handling."""
        async with StandaloneAsyncBatchTranscriber(
            use_stub=True,
            max_concurrent_batches=2,
            batch_size=4
        ) as sabt:
            # Submit chunk with metadata
            metadata = {"source": "test", "timestamp": time.time()}
            seq_id = await sabt.submit_audio(dummy_audio_chunks[0], metadata=metadata)
            
            # Get result
            result = await sabt.get_result(seq_id, timeout=30)
            
            assert result.metadata == metadata


class TestAsyncBatchTranscriberIntegration:
    """Integration tests for async batch transcription."""

    @pytest.mark.asyncio
    async def test_async_vs_traditional_performance(self):
        """Test that async transcriber performs at least as well as traditional."""
        # Generate test data
        test_chunks = [bytes([i] * 1000) for i in range(10)]
        
        # Test traditional batch transcriber
        from InstanceScrubber.batch_transcriber import BatchTranscriber
        
        start_time = time.time()
        with BatchTranscriber(use_stub=True, max_workers=4) as bt:
            for chunk in test_chunks:
                bt.submit_slice(chunk)
            traditional_result = bt.finalise(timeout_per_slice=30)
        traditional_time = time.time() - start_time
        
        # Test async batch transcriber
        start_time = time.time()
        async with AsyncBatchTranscriber(use_stub=True, max_concurrent=8) as abt:
            for chunk in test_chunks:
                await abt.submit_slice_async(chunk)
            async_result = await abt.finalise_async(timeout=30)
        async_time = time.time() - start_time
        
        # Results should be the same
        assert traditional_result == async_result
        
        # Async should be at least competitive (allow some tolerance)
        assert async_time <= traditional_time * 2.0  # Allow 2x tolerance for test environment

    @pytest.mark.asyncio
    async def test_benchmark_script_functionality(self):
        """Test that the benchmark script components work correctly."""
        # Import benchmark components
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        
        try:
            from benchmark_async_transcription import TranscriptionBenchmark
            
            # Create benchmark instance
            benchmark = TranscriptionBenchmark(use_stub=True, verbose=False)
            
            # Test that test audio generation works
            assert len(benchmark.test_audio_chunks) > 0
            assert all(isinstance(chunk, bytes) for chunk in benchmark.test_audio_chunks)
            
            # Test traditional benchmark (single iteration)
            traditional_results = benchmark.benchmark_traditional_batch_transcriber(iterations=1)
            assert traditional_results["method"] == "traditional_batch_transcriber"
            assert traditional_results["iterations"] == 1
            assert len(traditional_results["results"]) == 1
            
            # Test async benchmark (single iteration)
            async_results = await benchmark.benchmark_async_batch_transcriber(iterations=1)
            assert async_results["method"] == "async_batch_transcriber"
            assert async_results["iterations"] == 1
            assert len(async_results["results"]) == 1
            
        except ImportError:
            pytest.skip("Benchmark script not available")


def test_task52_integration():
    """Integration test for Task 52: Complete async batch transcription workflow."""
    async def run_integration_test():
        # Test data
        test_chunks = [bytes([i] * 800) for i in range(6)]
        
        # Test the complete async workflow
        async with AsyncBatchTranscriber(use_stub=True, max_concurrent=4) as abt:
            # Submit all chunks
            sequence_ids = []
            for chunk in test_chunks:
                seq_id = await abt.submit_slice_async(chunk)
                sequence_ids.append(seq_id)
            
            # Finalize
            result_text = await abt.finalise_async(timeout=30)
            
            # Get performance stats
            stats = abt.get_performance_stats()
            
            # Verify results
            assert len(sequence_ids) == len(test_chunks)
            assert result_text == " ".join(["hello world"] * len(test_chunks))
            assert stats["total_processed"] == len(test_chunks)
            assert stats["throughput_slices_per_second"] > 0
            
            # Test standalone async transcriber
            async with StandaloneAsyncBatchTranscriber(
                use_stub=True,
                max_concurrent_batches=2,
                batch_size=3
            ) as sabt:
                # Submit chunks
                for chunk in test_chunks:
                    await sabt.submit_audio(chunk)
                
                # Get all results
                results = await sabt.get_all_results(timeout=30)
                
                # Verify results
                assert len(results) == len(test_chunks)
                assert all(result.success for result in results)
                
                combined_text = " ".join(result.text for result in results)
                assert combined_text == " ".join(["hello world"] * len(test_chunks))
    
    # Run the async test
    asyncio.run(run_integration_test())
