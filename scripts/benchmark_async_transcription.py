#!/usr/bin/env python3
"""Benchmark script for Task 52.2: Async Batch Transcription Performance

This script benchmarks the throughput improvements of the async batch
transcription pipeline compared to the traditional thread-based approach.

Usage:
    python scripts/benchmark_async_transcription.py [--output baseline.json] [--iterations 10]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from InstanceScrubber.batch_transcriber import BatchTranscriber, AsyncBatchTranscriber
    from InstanceScrubber.async_batch_transcriber import AsyncBatchTranscriber as StandaloneAsyncBatchTranscriber
except ImportError as exc:
    print(f"Error importing modules: {exc}")
    print("Please run this script from the project root directory.")
    sys.exit(1)


class TranscriptionBenchmark:
    """Benchmarks transcription performance."""
    
    def __init__(self, use_stub: bool = True, verbose: bool = False):
        self.use_stub = use_stub
        self.verbose = verbose
        
        # Setup logging
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=level, format='%(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Generate test audio data
        self.test_audio_chunks = self._generate_test_audio()

    def _generate_test_audio(self) -> List[bytes]:
        """Generate test audio chunks for benchmarking."""
        # Generate dummy PCM audio data (16-bit, 16kHz, 10 seconds each)
        chunk_size = 16000 * 2 * 10  # 10 seconds of 16-bit audio at 16kHz
        
        chunks = []
        for i in range(20):  # 20 chunks = ~3.3 minutes of audio
            # Create some variation in the data
            chunk = bytes([(i * 17 + j) % 256 for j in range(chunk_size)])
            chunks.append(chunk)
        
        self.logger.info("Generated %d test audio chunks (%d bytes each)", len(chunks), chunk_size)
        return chunks

    def benchmark_traditional_batch_transcriber(self, iterations: int = 5) -> Dict[str, Any]:
        """Benchmark the traditional thread-based BatchTranscriber."""
        self.logger.info("Benchmarking traditional BatchTranscriber...")
        
        results = []
        
        for iteration in range(iterations):
            start_time = time.time()
            
            with BatchTranscriber(use_stub=self.use_stub, max_workers=4) as bt:
                # Submit all chunks
                for chunk in self.test_audio_chunks:
                    bt.submit_slice(chunk)
                
                # Wait for completion
                full_text = bt.finalise(timeout_per_slice=30)
                
            end_time = time.time()
            duration = end_time - start_time
            
            result = {
                "iteration": iteration + 1,
                "duration": duration,
                "chunks_processed": len(self.test_audio_chunks),
                "throughput": len(self.test_audio_chunks) / duration,
                "text_length": len(full_text),
            }
            
            results.append(result)
            self.logger.info("Traditional iteration %d: %.2fs (%.2f chunks/s)", 
                           iteration + 1, duration, result["throughput"])
        
        # Calculate statistics
        durations = [r["duration"] for r in results]
        throughputs = [r["throughput"] for r in results]
        
        return {
            "method": "traditional_batch_transcriber",
            "iterations": iterations,
            "results": results,
            "statistics": {
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "avg_throughput": sum(throughputs) / len(throughputs),
                "max_throughput": max(throughputs),
                "min_throughput": min(throughputs),
            }
        }

    async def benchmark_async_batch_transcriber(self, iterations: int = 5) -> Dict[str, Any]:
        """Benchmark the async BatchTranscriber."""
        self.logger.info("Benchmarking async BatchTranscriber...")
        
        results = []
        
        for iteration in range(iterations):
            start_time = time.time()
            
            async with AsyncBatchTranscriber(use_stub=self.use_stub, max_concurrent=8) as abt:
                # Submit all chunks
                sequence_ids = []
                for chunk in self.test_audio_chunks:
                    seq_id = await abt.submit_slice_async(chunk)
                    sequence_ids.append(seq_id)
                
                # Wait for completion
                full_text = await abt.finalise_async(timeout=60)
                
                # Get performance stats
                perf_stats = abt.get_performance_stats()
                
            end_time = time.time()
            duration = end_time - start_time
            
            result = {
                "iteration": iteration + 1,
                "duration": duration,
                "chunks_processed": len(self.test_audio_chunks),
                "throughput": len(self.test_audio_chunks) / duration,
                "text_length": len(full_text),
                "performance_stats": perf_stats,
            }
            
            results.append(result)
            self.logger.info("Async iteration %d: %.2fs (%.2f chunks/s)", 
                           iteration + 1, duration, result["throughput"])
        
        # Calculate statistics
        durations = [r["duration"] for r in results]
        throughputs = [r["throughput"] for r in results]
        
        return {
            "method": "async_batch_transcriber",
            "iterations": iterations,
            "results": results,
            "statistics": {
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "avg_throughput": sum(throughputs) / len(throughputs),
                "max_throughput": max(throughputs),
                "min_throughput": min(throughputs),
            }
        }

    async def benchmark_standalone_async_transcriber(self, iterations: int = 5) -> Dict[str, Any]:
        """Benchmark the standalone async batch transcriber."""
        self.logger.info("Benchmarking standalone async batch transcriber...")
        
        results = []
        
        for iteration in range(iterations):
            start_time = time.time()
            
            async with StandaloneAsyncBatchTranscriber(
                use_stub=self.use_stub,
                max_concurrent_batches=4,
                batch_size=8
            ) as sabt:
                # Submit all chunks
                sequence_ids = []
                for chunk in self.test_audio_chunks:
                    seq_id = await sabt.submit_audio(chunk)
                    sequence_ids.append(seq_id)
                
                # Get all results
                batch_results = await sabt.get_all_results(timeout=60)
                
                # Combine text
                full_text = " ".join(result.text for result in batch_results if result.success)
                
                # Get performance stats
                perf_stats = sabt.get_performance_stats()
                
            end_time = time.time()
            duration = end_time - start_time
            
            result = {
                "iteration": iteration + 1,
                "duration": duration,
                "chunks_processed": len(self.test_audio_chunks),
                "throughput": len(self.test_audio_chunks) / duration,
                "text_length": len(full_text),
                "performance_stats": perf_stats,
                "success_rate": sum(1 for r in batch_results if r.success) / len(batch_results),
            }
            
            results.append(result)
            self.logger.info("Standalone async iteration %d: %.2fs (%.2f chunks/s)", 
                           iteration + 1, duration, result["throughput"])
        
        # Calculate statistics
        durations = [r["duration"] for r in results]
        throughputs = [r["throughput"] for r in results]
        
        return {
            "method": "standalone_async_batch_transcriber",
            "iterations": iterations,
            "results": results,
            "statistics": {
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "avg_throughput": sum(throughputs) / len(throughputs),
                "max_throughput": max(throughputs),
                "min_throughput": min(throughputs),
            }
        }

    async def run_full_benchmark(self, iterations: int = 5) -> Dict[str, Any]:
        """Run complete benchmark comparing all methods."""
        self.logger.info("Starting full benchmark with %d iterations...", iterations)
        
        # Benchmark traditional approach
        traditional_results = self.benchmark_traditional_batch_transcriber(iterations)
        
        # Benchmark async approaches
        async_results = await self.benchmark_async_batch_transcriber(iterations)
        standalone_async_results = await self.benchmark_standalone_async_transcriber(iterations)
        
        # Calculate improvements
        traditional_throughput = traditional_results["statistics"]["avg_throughput"]
        async_throughput = async_results["statistics"]["avg_throughput"]
        standalone_throughput = standalone_async_results["statistics"]["avg_throughput"]
        
        improvement_async = (async_throughput / traditional_throughput - 1) * 100
        improvement_standalone = (standalone_throughput / traditional_throughput - 1) * 100
        
        return {
            "benchmark_timestamp": time.time(),
            "test_configuration": {
                "use_stub": self.use_stub,
                "test_chunks": len(self.test_audio_chunks),
                "iterations": iterations,
            },
            "results": {
                "traditional": traditional_results,
                "async": async_results,
                "standalone_async": standalone_async_results,
            },
            "performance_comparison": {
                "traditional_throughput": traditional_throughput,
                "async_throughput": async_throughput,
                "standalone_async_throughput": standalone_throughput,
                "async_improvement_percent": improvement_async,
                "standalone_improvement_percent": improvement_standalone,
            }
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Benchmark async batch transcription performance")
    parser.add_argument(
        "--output",
        type=Path,
        default="benchmark_results.json",
        help="Output file for benchmark results"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations per benchmark"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Run benchmark
    benchmark = TranscriptionBenchmark(use_stub=True, verbose=args.verbose)
    results = await benchmark.run_full_benchmark(args.iterations)
    
    # Save results
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 60)
    
    comparison = results["performance_comparison"]
    print(f"Traditional throughput: {comparison['traditional_throughput']:.2f} chunks/s")
    print(f"Async throughput: {comparison['async_throughput']:.2f} chunks/s")
    print(f"Standalone async throughput: {comparison['standalone_async_throughput']:.2f} chunks/s")
    print()
    print(f"Async improvement: {comparison['async_improvement_percent']:+.1f}%")
    print(f"Standalone async improvement: {comparison['standalone_improvement_percent']:+.1f}%")
    print()
    print(f"Results saved to: {args.output}")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
