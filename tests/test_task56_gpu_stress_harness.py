"""Comprehensive tests for Task 56 - GPU Stress Test Harness.

This test suite validates the GPU stress testing functionality including:
- VRAM leak detection with configurable thresholds
- Safe stress testing without hardware damage
- Real-time GPU monitoring and safety checks
- Comprehensive reporting and metrics collection
"""

import pytest
import time
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from benchmarks.gpu_stress import (
    GPUStressHarness, 
    StressTestResult, 
    GPUMetrics,
    run_stress_test
)


class TestGPUMetrics:
    """Test GPU metrics data structure."""
    
    def test_gpu_metrics_creation(self):
        """Test GPUMetrics dataclass creation."""
        metrics = GPUMetrics(
            timestamp=time.time(),
            temperature_gpu=75,
            temperature_memory=85,
            memory_total_mb=10240,
            memory_used_mb=2048,
            memory_free_mb=8192,
            utilization_gpu=50,
            utilization_memory=30,
            power_draw_w=250.5,
            clock_graphics_mhz=1800,
            clock_memory_mhz=9500
        )
        
        assert metrics.temperature_gpu == 75
        assert metrics.memory_total_mb == 10240
        assert metrics.power_draw_w == 250.5


class TestStressTestResult:
    """Test stress test result data structure."""
    
    def test_stress_test_result_creation(self):
        """Test StressTestResult dataclass creation."""
        result = StressTestResult(
            success=True,
            total_cycles=100,
            completed_cycles=100,
            initial_memory_mb=1024,
            final_memory_mb=1028,
            peak_memory_mb=2048,
            memory_leak_mb=4.0,
            leak_threshold_exceeded=False,
            average_load_time_s=2.5,
            average_unload_time_s=1.2,
            peak_temperature_c=78,
            peak_power_w=275.0,
            error_message=None,
            metrics_history=[],
            test_duration_s=450.0
        )
        
        assert result.success is True
        assert result.memory_leak_mb == 4.0
        assert result.leak_threshold_exceeded is False


class TestGPUStressHarness:
    """Test GPU stress harness functionality."""
    
    @pytest.fixture
    def mock_nvml(self):
        """Mock pynvml for testing."""
        with patch('benchmarks.gpu_stress.pynvml') as mock_pynvml:
            # Mock memory info
            mock_mem_info = Mock()
            mock_mem_info.total = 10 * 1024 * 1024 * 1024  # 10GB
            mock_mem_info.used = 2 * 1024 * 1024 * 1024   # 2GB
            mock_mem_info.free = 8 * 1024 * 1024 * 1024   # 8GB
            
            # Mock utilization
            mock_util = Mock()
            mock_util.gpu = 50
            mock_util.memory = 30
            
            # Mock device handle
            mock_handle = Mock()
            
            # Configure mock methods
            mock_pynvml.nvmlInit.return_value = None
            mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
            mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_mem_info
            mock_pynvml.nvmlDeviceGetTemperature.return_value = 75
            mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_util
            mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 250000  # 250W in mW
            mock_pynvml.nvmlDeviceGetClockInfo.return_value = 1800
            mock_pynvml.NVML_TEMPERATURE_GPU = 0
            mock_pynvml.NVML_TEMPERATURE_MEMORY = 1
            mock_pynvml.NVML_CLOCK_GRAPHICS = 0
            mock_pynvml.NVML_CLOCK_MEM = 1
            
            yield mock_pynvml
    
    @pytest.fixture
    def mock_transcription_engine(self):
        """Mock TranscriptionEngine for testing."""
        with patch('benchmarks.gpu_stress.TranscriptionEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.load_model.return_value = None
            mock_engine.unload_model.return_value = None
            mock_engine_class.return_value = mock_engine
            yield mock_engine_class
    
    def test_harness_initialization(self, mock_nvml):
        """Test GPU stress harness initialization."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', True):
            harness = GPUStressHarness(
                leak_threshold_mb=5.0,
                max_temperature_c=85,
                cooldown_seconds=0.5
            )
            
            assert harness.leak_threshold_mb == 5.0
            assert harness.max_temperature_c == 85
            assert harness.cooldown_seconds == 0.5
            assert harness._handle is not None
    
    def test_harness_without_nvml(self):
        """Test harness initialization without NVML."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', False):
            harness = GPUStressHarness()
            assert harness._handle is None
    
    def test_get_gpu_metrics(self, mock_nvml):
        """Test GPU metrics collection."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', True):
            harness = GPUStressHarness()
            metrics = harness._get_gpu_metrics()
            
            assert metrics is not None
            assert metrics.temperature_gpu == 75
            assert metrics.memory_total_mb == 10240  # 10GB in MB
            assert metrics.memory_used_mb == 2048    # 2GB in MB
            assert metrics.power_draw_w == 250.0     # 250W
    
    def test_safety_limits_check(self, mock_nvml):
        """Test safety limits checking."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', True):
            harness = GPUStressHarness(max_temperature_c=80, max_power_w=300.0)
            
            # Safe metrics
            safe_metrics = GPUMetrics(
                timestamp=time.time(),
                temperature_gpu=75,
                temperature_memory=None,
                memory_total_mb=10240,
                memory_used_mb=2048,
                memory_free_mb=8192,
                utilization_gpu=50,
                utilization_memory=30,
                power_draw_w=250.0,
                clock_graphics_mhz=1800,
                clock_memory_mhz=9500
            )
            
            assert harness._check_safety_limits(safe_metrics) is True
            
            # Unsafe temperature
            unsafe_temp_metrics = safe_metrics
            unsafe_temp_metrics.temperature_gpu = 85
            assert harness._check_safety_limits(unsafe_temp_metrics) is False
            
            # Unsafe power
            unsafe_power_metrics = safe_metrics
            unsafe_power_metrics.temperature_gpu = 75  # Reset temperature
            unsafe_power_metrics.power_draw_w = 350.0
            assert harness._check_safety_limits(unsafe_power_metrics) is False
    
    def test_stress_test_with_stub(self, mock_nvml, mock_transcription_engine):
        """Test stress test with stub model."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', True), \
             patch('benchmarks.gpu_stress._NEMO_AVAILABLE', True):
            
            harness = GPUStressHarness(leak_threshold_mb=5.0, cooldown_seconds=0.01)
            
            # Simulate memory increase over cycles
            memory_values = [2048 + i * 0.5 for i in range(20)]  # Small increase each cycle
            mock_nvml.nvmlDeviceGetMemoryInfo.side_effect = [
                Mock(total=10*1024*1024*1024, used=int(val*1024*1024), free=(10240-int(val))*1024*1024)
                for val in memory_values
            ]
            
            result = harness.run_stress_test(cycles=10, use_stub=True)
            
            assert result.total_cycles == 10
            assert result.completed_cycles == 10
            assert result.success is True
            assert len(result.metrics_history) > 0
            assert result.average_load_time_s >= 0
            assert result.average_unload_time_s >= 0
    
    def test_stress_test_memory_leak_detection(self, mock_nvml, mock_transcription_engine):
        """Test memory leak detection."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', True), \
             patch('benchmarks.gpu_stress._NEMO_AVAILABLE', True):
            
            harness = GPUStressHarness(leak_threshold_mb=5.0, cooldown_seconds=0.01)
            
            # Simulate significant memory leak
            initial_memory = 2048
            final_memory = 2055  # 7MB leak
            
            memory_call_count = 0
            def mock_memory_info():
                nonlocal memory_call_count
                memory_call_count += 1
                if memory_call_count <= 5:
                    used = initial_memory * 1024 * 1024
                else:
                    used = final_memory * 1024 * 1024
                return Mock(
                    total=10*1024*1024*1024,
                    used=used,
                    free=(10240*1024*1024) - used
                )
            
            mock_nvml.nvmlDeviceGetMemoryInfo.side_effect = mock_memory_info
            
            result = harness.run_stress_test(cycles=5, use_stub=True)
            
            assert result.memory_leak_mb == 7.0
            assert result.leak_threshold_exceeded is True
            assert result.success is False
    
    def test_stress_test_temperature_safety(self, mock_nvml, mock_transcription_engine):
        """Test temperature safety limits."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', True), \
             patch('benchmarks.gpu_stress._NEMO_AVAILABLE', True):
            
            harness = GPUStressHarness(max_temperature_c=80, cooldown_seconds=0.01)
            
            # Simulate overheating
            temp_call_count = 0
            def mock_temperature(handle, sensor):
                nonlocal temp_call_count
                temp_call_count += 1
                return 85 if temp_call_count > 3 else 75  # Overheat after 3 calls
            
            mock_nvml.nvmlDeviceGetTemperature.side_effect = mock_temperature
            
            result = harness.run_stress_test(cycles=10, use_stub=True)
            
            assert result.success is False
            assert "Safety limits exceeded" in result.error_message
            assert result.completed_cycles < 10
    
    def test_stress_test_model_load_failure(self, mock_nvml, mock_transcription_engine):
        """Test handling of model load failures."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', True), \
             patch('benchmarks.gpu_stress._NEMO_AVAILABLE', True):
            
            harness = GPUStressHarness(cooldown_seconds=0.01)
            
            # Make model loading fail
            mock_engine = mock_transcription_engine.return_value
            mock_engine.load_model.side_effect = RuntimeError("CUDA out of memory")
            
            result = harness.run_stress_test(cycles=5, use_stub=True)
            
            assert result.success is False
            assert "Model load failed" in result.error_message
            assert result.completed_cycles == 0


class TestStressTestFunction:
    """Test the standalone stress test function."""
    
    @pytest.fixture
    def temp_output_file(self):
        """Create temporary output file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            yield f.name
        Path(f.name).unlink(missing_ok=True)
    
    def test_run_stress_test_function(self, temp_output_file):
        """Test the run_stress_test function."""
        with patch('benchmarks.gpu_stress.GPUStressHarness') as mock_harness_class:
            mock_harness = Mock()
            mock_result = StressTestResult(
                success=True,
                total_cycles=5,
                completed_cycles=5,
                initial_memory_mb=2048,
                final_memory_mb=2050,
                peak_memory_mb=2100,
                memory_leak_mb=2.0,
                leak_threshold_exceeded=False,
                average_load_time_s=1.5,
                average_unload_time_s=0.8,
                peak_temperature_c=76,
                peak_power_w=260.0,
                error_message=None,
                metrics_history=[],
                test_duration_s=25.0
            )
            
            mock_harness.run_stress_test.return_value = mock_result
            mock_harness_class.return_value = mock_harness
            
            result = run_stress_test(
                cycles=5,
                leak_threshold_mb=3.0,
                use_stub=True,
                output_file=temp_output_file
            )
            
            assert result.success is True
            assert result.total_cycles == 5
            assert result.memory_leak_mb == 2.0
            
            # Check output file was created
            assert Path(temp_output_file).exists()
            
            # Verify JSON content
            with open(temp_output_file, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data['success'] is True
            assert saved_data['total_cycles'] == 5
            assert saved_data['memory_leak_mb'] == 2.0


class TestIntegration:
    """Integration tests for the complete stress testing workflow."""
    
    def test_full_workflow_with_mocks(self):
        """Test complete workflow with all components mocked."""
        with patch('benchmarks.gpu_stress._NVML_AVAILABLE', True), \
             patch('benchmarks.gpu_stress._NEMO_AVAILABLE', True), \
             patch('benchmarks.gpu_stress.pynvml') as mock_pynvml, \
             patch('benchmarks.gpu_stress.TranscriptionEngine') as mock_engine_class:
            
            # Setup mocks
            mock_mem_info = Mock()
            mock_mem_info.total = 10 * 1024 * 1024 * 1024
            mock_mem_info.used = 2 * 1024 * 1024 * 1024
            mock_mem_info.free = 8 * 1024 * 1024 * 1024
            
            mock_util = Mock()
            mock_util.gpu = 45
            mock_util.memory = 25
            
            mock_pynvml.nvmlInit.return_value = None
            mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = Mock()
            mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_mem_info
            mock_pynvml.nvmlDeviceGetTemperature.return_value = 72
            mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_util
            mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 240000
            mock_pynvml.nvmlDeviceGetClockInfo.return_value = 1750
            mock_pynvml.NVML_TEMPERATURE_GPU = 0
            mock_pynvml.NVML_CLOCK_GRAPHICS = 0
            mock_pynvml.NVML_CLOCK_MEM = 1
            
            mock_engine = Mock()
            mock_engine.load_model.return_value = None
            mock_engine.unload_model.return_value = None
            mock_engine_class.return_value = mock_engine
            
            # Run test
            harness = GPUStressHarness(leak_threshold_mb=10.0, cooldown_seconds=0.01)
            result = harness.run_stress_test(cycles=3, use_stub=True)
            
            # Verify results
            assert result.success is True
            assert result.completed_cycles == 3
            assert result.memory_leak_mb == 0.0  # No leak simulated
            assert result.leak_threshold_exceeded is False
            assert len(result.metrics_history) > 0
            
            # Verify engine was called correctly
            assert mock_engine.load_model.call_count == 3
            assert mock_engine.unload_model.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
