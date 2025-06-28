"""GPU Stress Test Harness for Task 56 - RTX 3080 VRAM Leak Detection.

This module implements comprehensive GPU stress testing by loading and unloading
the Parakeet model 100 times while monitoring VRAM usage. It detects memory leaks
exceeding 5MB and provides detailed reporting of GPU performance metrics.

Key Features:
- Safe stress testing without hardware damage
- VRAM leak detection with configurable thresholds
- Real-time GPU monitoring with pynvml
- Comprehensive reporting and logging
- Temperature and power monitoring for safety
"""

from __future__ import annotations

import gc
import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import sys

try:
    import pynvml
    _NVML_AVAILABLE = True
except ImportError:
    pynvml = None
    _NVML_AVAILABLE = False

# Import NeMo and transcription engine
try:
    import sys
    import os
    # Add the project root to the path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from InstanceScrubber.transcription_worker import TranscriptionEngine
    _NEMO_AVAILABLE = True
except ImportError:
    TranscriptionEngine = None
    _NEMO_AVAILABLE = False

__all__ = ["GPUStressHarness", "StressTestResult", "run_stress_test"]


@dataclass
class GPUMetrics:
    """GPU metrics snapshot."""
    timestamp: float
    temperature_gpu: int
    temperature_memory: Optional[int]
    memory_total_mb: int
    memory_used_mb: int
    memory_free_mb: int
    utilization_gpu: int
    utilization_memory: int
    power_draw_w: Optional[float]
    clock_graphics_mhz: int
    clock_memory_mhz: int


@dataclass
class StressTestResult:
    """Results from GPU stress test."""
    success: bool
    total_cycles: int
    completed_cycles: int
    initial_memory_mb: int
    final_memory_mb: int
    peak_memory_mb: int
    memory_leak_mb: float
    leak_threshold_exceeded: bool
    average_load_time_s: float
    average_unload_time_s: float
    peak_temperature_c: int
    peak_power_w: Optional[float]
    error_message: Optional[str]
    metrics_history: List[GPUMetrics]
    test_duration_s: float


class GPUStressHarness:
    """GPU stress testing harness for VRAM leak detection."""
    
    def __init__(self, 
                 leak_threshold_mb: float = 5.0,
                 max_temperature_c: int = 90,
                 max_power_w: Optional[float] = None,
                 cooldown_seconds: float = 1.0):
        """Initialize GPU stress harness.
        
        Args:
            leak_threshold_mb: Maximum allowed VRAM leak in MB
            max_temperature_c: Maximum safe GPU temperature
            max_power_w: Maximum safe power draw (None for no limit)
            cooldown_seconds: Cooldown time between cycles
        """
        self.leak_threshold_mb = leak_threshold_mb
        self.max_temperature_c = max_temperature_c
        self.max_power_w = max_power_w
        self.cooldown_seconds = cooldown_seconds
        
        self._log = logging.getLogger(__name__)
        self._handle: Optional[Any] = None
        self._init_nvml()
        
    def _init_nvml(self) -> None:
        """Initialize NVML for GPU monitoring."""
        if not _NVML_AVAILABLE:
            self._log.warning("pynvml not available - GPU monitoring disabled")
            return
            
        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._log.info("NVML initialized successfully")
        except Exception as exc:
            self._log.warning(f"NVML initialization failed: {exc}")
            self._handle = None
    
    def _get_gpu_metrics(self) -> Optional[GPUMetrics]:
        """Get current GPU metrics."""
        if self._handle is None:
            return None
            
        try:
            # Memory info
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            
            # Temperature
            temp_gpu = pynvml.nvmlDeviceGetTemperature(self._handle, pynvml.NVML_TEMPERATURE_GPU)
            temp_memory = None
            try:
                temp_memory = pynvml.nvmlDeviceGetTemperature(self._handle, pynvml.NVML_TEMPERATURE_MEMORY)
            except:
                pass  # Memory temperature not available on all GPUs
            
            # Utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            
            # Power
            power_draw = None
            try:
                power_draw = pynvml.nvmlDeviceGetPowerUsage(self._handle) / 1000.0  # Convert mW to W
            except:
                pass  # Power monitoring not available on all GPUs
            
            # Clock speeds
            clock_graphics = pynvml.nvmlDeviceGetClockInfo(self._handle, pynvml.NVML_CLOCK_GRAPHICS)
            clock_memory = pynvml.nvmlDeviceGetClockInfo(self._handle, pynvml.NVML_CLOCK_MEM)
            
            return GPUMetrics(
                timestamp=time.time(),
                temperature_gpu=temp_gpu,
                temperature_memory=temp_memory,
                memory_total_mb=mem_info.total // (1024 * 1024),
                memory_used_mb=mem_info.used // (1024 * 1024),
                memory_free_mb=mem_info.free // (1024 * 1024),
                utilization_gpu=util.gpu,
                utilization_memory=util.memory,
                power_draw_w=power_draw,
                clock_graphics_mhz=clock_graphics,
                clock_memory_mhz=clock_memory
            )
        except Exception as exc:
            self._log.warning(f"Failed to get GPU metrics: {exc}")
            return None
    
    def _check_safety_limits(self, metrics: GPUMetrics) -> bool:
        """Check if GPU is within safe operating limits."""
        if metrics.temperature_gpu > self.max_temperature_c:
            self._log.error(f"GPU temperature {metrics.temperature_gpu}°C exceeds limit {self.max_temperature_c}°C")
            return False
            
        if self.max_power_w and metrics.power_draw_w and metrics.power_draw_w > self.max_power_w:
            self._log.error(f"GPU power {metrics.power_draw_w}W exceeds limit {self.max_power_w}W")
            return False
            
        return True
    
    def run_stress_test(self, cycles: int = 100, use_stub: bool = False) -> StressTestResult:
        """Run GPU stress test with model loading/unloading cycles.
        
        Args:
            cycles: Number of load/unload cycles to perform
            use_stub: Use stub model for testing (no actual GPU load)
            
        Returns:
            StressTestResult with detailed metrics and results
        """
        self._log.info(f"Starting GPU stress test: {cycles} cycles, leak threshold: {self.leak_threshold_mb}MB")
        
        start_time = time.time()
        metrics_history: List[GPUMetrics] = []
        load_times: List[float] = []
        unload_times: List[float] = []
        
        # Get initial metrics
        initial_metrics = self._get_gpu_metrics()
        if initial_metrics:
            metrics_history.append(initial_metrics)
            initial_memory_mb = initial_metrics.memory_used_mb
        else:
            initial_memory_mb = 0
            
        peak_memory_mb = initial_memory_mb
        peak_temperature_c = initial_metrics.temperature_gpu if initial_metrics else 0
        peak_power_w = initial_metrics.power_draw_w if initial_metrics else None
        
        completed_cycles = 0
        error_message = None
        
        try:
            for cycle in range(cycles):
                self._log.info(f"Cycle {cycle + 1}/{cycles}")
                
                # Create fresh engine for each cycle
                if TranscriptionEngine is None:
                    raise RuntimeError("TranscriptionEngine not available")
                engine = TranscriptionEngine()
                
                # Load model and measure time
                load_start = time.time()
                try:
                    engine.load_model(use_stub=use_stub)
                    load_time = time.time() - load_start
                    load_times.append(load_time)
                except Exception as exc:
                    error_message = f"Model load failed at cycle {cycle + 1}: {exc}"
                    self._log.error(error_message)
                    break
                
                # Get metrics after load
                metrics = self._get_gpu_metrics()
                if metrics:
                    metrics_history.append(metrics)
                    peak_memory_mb = max(peak_memory_mb, metrics.memory_used_mb)
                    peak_temperature_c = max(peak_temperature_c, metrics.temperature_gpu)
                    if metrics.power_draw_w:
                        peak_power_w = max(peak_power_w or 0, metrics.power_draw_w)
                    
                    # Check safety limits
                    if not self._check_safety_limits(metrics):
                        error_message = f"Safety limits exceeded at cycle {cycle + 1}"
                        break
                
                # Brief pause to let GPU settle
                time.sleep(0.1)
                
                # Unload model and measure time
                unload_start = time.time()
                try:
                    engine.unload_model()
                    unload_time = time.time() - unload_start
                    unload_times.append(unload_time)
                except Exception as exc:
                    error_message = f"Model unload failed at cycle {cycle + 1}: {exc}"
                    self._log.error(error_message)
                    break
                
                # Force garbage collection
                del engine
                gc.collect()
                
                # Cooldown period
                if self.cooldown_seconds > 0:
                    time.sleep(self.cooldown_seconds)
                
                # Get metrics after unload
                metrics = self._get_gpu_metrics()
                if metrics:
                    metrics_history.append(metrics)
                
                completed_cycles += 1
                
        except KeyboardInterrupt:
            error_message = "Test interrupted by user"
            self._log.warning(error_message)
        except Exception as exc:
            error_message = f"Unexpected error: {exc}"
            self._log.error(error_message)
        
        # Get final metrics
        final_metrics = self._get_gpu_metrics()
        if final_metrics:
            metrics_history.append(final_metrics)
            final_memory_mb = final_metrics.memory_used_mb
        else:
            final_memory_mb = initial_memory_mb
        
        # Calculate results
        test_duration = time.time() - start_time
        memory_leak_mb = final_memory_mb - initial_memory_mb
        leak_threshold_exceeded = memory_leak_mb > self.leak_threshold_mb
        
        avg_load_time = sum(load_times) / len(load_times) if load_times else 0.0
        avg_unload_time = sum(unload_times) / len(unload_times) if unload_times else 0.0
        
        success = (completed_cycles == cycles and 
                  not leak_threshold_exceeded and 
                  error_message is None)
        
        result = StressTestResult(
            success=success,
            total_cycles=cycles,
            completed_cycles=completed_cycles,
            initial_memory_mb=initial_memory_mb,
            final_memory_mb=final_memory_mb,
            peak_memory_mb=peak_memory_mb,
            memory_leak_mb=memory_leak_mb,
            leak_threshold_exceeded=leak_threshold_exceeded,
            average_load_time_s=avg_load_time,
            average_unload_time_s=avg_unload_time,
            peak_temperature_c=peak_temperature_c,
            peak_power_w=peak_power_w,
            error_message=error_message,
            metrics_history=metrics_history,
            test_duration_s=test_duration
        )
        
        self._log_results(result)
        return result
    
    def _log_results(self, result: StressTestResult) -> None:
        """Log stress test results."""
        self._log.info("=== GPU Stress Test Results ===")
        self._log.info(f"Success: {result.success}")
        self._log.info(f"Completed Cycles: {result.completed_cycles}/{result.total_cycles}")
        self._log.info(f"Memory Leak: {result.memory_leak_mb:.2f}MB (threshold: {self.leak_threshold_mb}MB)")
        self._log.info(f"Leak Threshold Exceeded: {result.leak_threshold_exceeded}")
        self._log.info(f"Average Load Time: {result.average_load_time_s:.3f}s")
        self._log.info(f"Average Unload Time: {result.average_unload_time_s:.3f}s")
        self._log.info(f"Peak Temperature: {result.peak_temperature_c}°C")
        if result.peak_power_w:
            self._log.info(f"Peak Power: {result.peak_power_w:.1f}W")
        self._log.info(f"Test Duration: {result.test_duration_s:.1f}s")
        
        if result.error_message:
            self._log.error(f"Error: {result.error_message}")


def run_stress_test(cycles: int = 100, 
                   leak_threshold_mb: float = 5.0,
                   use_stub: bool = False,
                   output_file: Optional[str] = None) -> StressTestResult:
    """Run GPU stress test and optionally save results.
    
    Args:
        cycles: Number of load/unload cycles
        leak_threshold_mb: VRAM leak threshold in MB
        use_stub: Use stub model for testing
        output_file: Optional file to save results JSON
        
    Returns:
        StressTestResult with detailed metrics
    """
    harness = GPUStressHarness(leak_threshold_mb=leak_threshold_mb)
    result = harness.run_stress_test(cycles=cycles, use_stub=use_stub)
    
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert result to JSON-serializable format
        result_dict = asdict(result)
        
        with open(output_path, 'w') as f:
            json.dump(result_dict, f, indent=2, default=str)
        
        logging.info(f"Results saved to {output_path}")
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GPU Stress Test Harness")
    parser.add_argument("--cycles", type=int, default=100, help="Number of load/unload cycles")
    parser.add_argument("--threshold", type=float, default=5.0, help="VRAM leak threshold in MB")
    parser.add_argument("--stub", action="store_true", help="Use stub model for testing")
    parser.add_argument("--output", type=str, help="Output file for results JSON")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check dependencies
    if not _NVML_AVAILABLE:
        logging.error("pynvml not available - cannot monitor GPU")
        sys.exit(1)
        
    if not _NEMO_AVAILABLE and not args.stub:
        logging.error("NeMo/TranscriptionEngine not available - use --stub for testing")
        sys.exit(1)
    
    # Run stress test
    result = run_stress_test(
        cycles=args.cycles,
        leak_threshold_mb=args.threshold,
        use_stub=args.stub,
        output_file=args.output
    )
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)
