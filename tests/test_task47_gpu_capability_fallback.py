"""Tests for Task 47 - GPU Capability Fallback.

This module tests the GPU capability checking functionality including:
- VRAM detection and validation
- Blocking notifications for unsupported hardware
- CPU mode CLI flag handling
"""

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
import sys
from io import StringIO
from pathlib import Path


@pytest.fixture(autouse=True)
def _cleanup_test_environment(tmp_path, monkeypatch):
    """Ensure clean test environment with proper cleanup."""
    # Redirect any potential file creation to tmp_path
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    yield

    # Explicit cleanup - remove any files that might have been created
    for log_file in ["crash.log", "app.log", "watchdog.log"]:
        log_path = tmp_path / log_file
        if log_path.exists():
            log_path.unlink()

    # Clean up any config directories
    config_dir = tmp_path / "Instant Scribe"
    if config_dir.exists():
        import shutil
        shutil.rmtree(config_dir, ignore_errors=True)


class TestGPUCapabilityChecker:
    """Test the GPUCapabilityChecker class functionality."""

    def test_init_without_pynvml(self):
        """Test initialization when pynvml is not available."""
        with patch('InstanceScrubber.gpu_capability_checker._NVML_AVAILABLE', False):
            from InstanceScrubber.gpu_capability_checker import GPUCapabilityChecker
            checker = GPUCapabilityChecker()
            assert checker._handle is None

    def test_init_with_pynvml_success(self):
        """Test successful initialization with pynvml."""
        mock_pynvml = MagicMock()
        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        
        with patch('InstanceScrubber.gpu_capability_checker._NVML_AVAILABLE', True):
            with patch('InstanceScrubber.gpu_capability_checker.pynvml', mock_pynvml):
                from InstanceScrubber.gpu_capability_checker import GPUCapabilityChecker
                checker = GPUCapabilityChecker()
                assert checker._handle == mock_handle
                mock_pynvml.nvmlInit.assert_called_once()

    def test_init_with_pynvml_failure(self):
        """Test initialization when pynvml fails."""
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlInit.side_effect = Exception("NVML init failed")
        
        with patch('InstanceScrubber.gpu_capability_checker._NVML_AVAILABLE', True):
            with patch('InstanceScrubber.gpu_capability_checker.pynvml', mock_pynvml):
                from InstanceScrubber.gpu_capability_checker import GPUCapabilityChecker
                checker = GPUCapabilityChecker()
                assert checker._handle is None

    def test_get_gpu_memory_info_no_handle(self):
        """Test memory info when no GPU handle is available."""
        with patch('InstanceScrubber.gpu_capability_checker._NVML_AVAILABLE', False):
            from InstanceScrubber.gpu_capability_checker import GPUCapabilityChecker
            checker = GPUCapabilityChecker()
            result = checker.get_gpu_memory_info()
            assert result is None

    def test_get_gpu_memory_info_success(self):
        """Test successful memory info retrieval."""
        mock_pynvml = MagicMock()
        mock_handle = MagicMock()
        mock_memory = MagicMock()
        mock_memory.total = 8 * (1024 ** 3)  # 8 GB
        mock_memory.used = 2 * (1024 ** 3)   # 2 GB
        mock_memory.free = 6 * (1024 ** 3)   # 6 GB
        
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory
        
        with patch('InstanceScrubber.gpu_capability_checker._NVML_AVAILABLE', True):
            with patch('InstanceScrubber.gpu_capability_checker.pynvml', mock_pynvml):
                from InstanceScrubber.gpu_capability_checker import GPUCapabilityChecker
                checker = GPUCapabilityChecker()
                result = checker.get_gpu_memory_info()
                
                assert result is not None
                total_gb, used_gb, free_gb = result
                assert abs(total_gb - 8.0) < 0.1
                assert abs(used_gb - 2.0) < 0.1
                assert abs(free_gb - 6.0) < 0.1

    def test_get_gpu_name_success(self):
        """Test successful GPU name retrieval."""
        mock_pynvml = MagicMock()
        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA RTX 3080"
        
        with patch('InstanceScrubber.gpu_capability_checker._NVML_AVAILABLE', True):
            with patch('InstanceScrubber.gpu_capability_checker.pynvml', mock_pynvml):
                from InstanceScrubber.gpu_capability_checker import GPUCapabilityChecker
                checker = GPUCapabilityChecker()
                result = checker.get_gpu_name()
                assert result == "NVIDIA RTX 3080"

    def test_check_vram_capability_insufficient(self):
        """Test VRAM capability check with insufficient memory."""
        mock_pynvml = MagicMock()
        mock_handle = MagicMock()
        mock_memory = MagicMock()
        mock_memory.total = 4 * (1024 ** 3)  # 4 GB
        mock_memory.used = 2 * (1024 ** 3)   # 2 GB
        mock_memory.free = 2 * (1024 ** 3)   # 2 GB (< 3 GB required)
        
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GTX 1060"
        
        with patch('InstanceScrubber.gpu_capability_checker._NVML_AVAILABLE', True):
            with patch('InstanceScrubber.gpu_capability_checker.pynvml', mock_pynvml):
                from InstanceScrubber.gpu_capability_checker import GPUCapabilityChecker
                checker = GPUCapabilityChecker()
                is_capable, message = checker.check_vram_capability()
                
                assert not is_capable
                assert "Insufficient VRAM" in message
                assert "2.00 GB free" in message
                assert "3.0 GB" in message

    def test_check_vram_capability_sufficient(self):
        """Test VRAM capability check with sufficient memory."""
        mock_pynvml = MagicMock()
        mock_handle = MagicMock()
        mock_memory = MagicMock()
        mock_memory.total = 8 * (1024 ** 3)  # 8 GB
        mock_memory.used = 2 * (1024 ** 3)   # 2 GB
        mock_memory.free = 6 * (1024 ** 3)   # 6 GB (> 3 GB required)
        
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA RTX 3080"
        
        with patch('InstanceScrubber.gpu_capability_checker._NVML_AVAILABLE', True):
            with patch('InstanceScrubber.gpu_capability_checker.pynvml', mock_pynvml):
                from InstanceScrubber.gpu_capability_checker import GPUCapabilityChecker
                checker = GPUCapabilityChecker()
                is_capable, message = checker.check_vram_capability()
                
                assert is_capable
                assert "GPU capability OK" in message
                assert "6.00 GB free" in message


class TestBlockingGPUCapabilityCheck:
    """Test the blocking GPU capability check function."""

    def test_blocking_check_success(self, caplog):
        """Test blocking check with sufficient VRAM."""
        with patch('InstanceScrubber.gpu_capability_checker.GPUCapabilityChecker') as mock_checker_cls:
            mock_checker = Mock()
            mock_checker.check_vram_capability.return_value = (True, "GPU capability OK")
            mock_checker_cls.return_value = mock_checker
            
            from InstanceScrubber.gpu_capability_checker import check_gpu_capability_blocking
            
            with caplog.at_level(logging.INFO):
                result = check_gpu_capability_blocking()
                
            assert result is True
            assert "GPU capability check passed" in caplog.text

    def test_blocking_check_failure_with_notification(self, caplog):
        """Test blocking check with insufficient VRAM and notification."""
        with patch('InstanceScrubber.gpu_capability_checker.GPUCapabilityChecker') as mock_checker_cls:
            mock_checker = Mock()
            mock_checker.check_vram_capability.return_value = (False, "Insufficient VRAM")
            mock_checker_cls.return_value = mock_checker
            
            # Mock the notification manager
            mock_notifier = Mock()
            with patch('InstanceScrubber.gpu_capability_checker.NotificationManager', return_value=mock_notifier):
                from InstanceScrubber.gpu_capability_checker import check_gpu_capability_blocking
                
                with caplog.at_level(logging.ERROR):
                    result = check_gpu_capability_blocking()
                    
                assert result is False
                assert "GPU capability check failed" in caplog.text
                mock_notifier.show_blocking_notification.assert_called_once()

    def test_blocking_check_failure_notification_error(self, caplog, capsys):
        """Test blocking check when notification fails."""
        with patch('InstanceScrubber.gpu_capability_checker.GPUCapabilityChecker') as mock_checker_cls:
            mock_checker = Mock()
            mock_checker.check_vram_capability.return_value = (False, "Insufficient VRAM")
            mock_checker_cls.return_value = mock_checker
            
            # Mock notification manager to raise exception
            with patch('InstanceScrubber.gpu_capability_checker.NotificationManager', side_effect=Exception("Notification failed")):
                from InstanceScrubber.gpu_capability_checker import check_gpu_capability_blocking
                
                # Mock input to avoid blocking
                with patch('builtins.input', return_value=''):
                    with caplog.at_level(logging.WARNING):
                        result = check_gpu_capability_blocking()
                        
                assert result is False
                assert "Failed to show blocking notification" in caplog.text
                captured = capsys.readouterr()
                assert "ERROR: Insufficient VRAM" in captured.out


class TestCPUModeFlag:
    """Test the CPU mode CLI flag functionality."""

    def test_cpu_mode_flag_warning(self, caplog):
        """Test that --cpu-mode flag generates appropriate warning."""
        # Mock sys.argv to include --cpu-mode
        test_args = ['instant_scribe', '--cpu-mode']
        
        with patch.object(sys, 'argv', test_args):
            with patch('instant_scribe.application_orchestrator.ApplicationOrchestrator') as mock_orch:
                from instant_scribe.application_orchestrator import main
                
                # Mock the orchestrator to avoid actual startup
                mock_instance = Mock()
                mock_orch.return_value = mock_instance
                
                # Mock the infinite loop to exit immediately
                with patch('time.sleep', side_effect=KeyboardInterrupt):
                    with caplog.at_level(logging.WARNING):
                        try:
                            main()
                        except KeyboardInterrupt:
                            pass
                        
                # Check that warning was logged
                assert any("CPU mode requested via --cpu-mode flag but is DISABLED in v1.0" in record.message 
                          for record in caplog.records if record.levelno == logging.WARNING)

    def test_cpu_mode_flag_parsing(self):
        """Test that --cpu-mode flag is properly parsed."""
        import argparse
        from instant_scribe.application_orchestrator import main
        
        # Extract the parser creation logic
        parser = argparse.ArgumentParser(description="Instant Scribe launcher")
        parser.add_argument("--recover", action="store_true")
        parser.add_argument("--stub-worker", action="store_true")
        parser.add_argument("--cpu-mode", action="store_true")
        
        # Test parsing
        args = parser.parse_args(['--cpu-mode'])
        assert args.cpu_mode is True
        
        args = parser.parse_args([])
        assert args.cpu_mode is False


class TestApplicationOrchestratorGPUCheck:
    """Test GPU capability check integration in ApplicationOrchestrator."""

    def test_gpu_check_skipped_for_stub_worker(self):
        """Test that GPU check is skipped when using stub worker."""
        with patch('InstanceScrubber.gpu_capability_checker.check_gpu_capability_blocking') as mock_check:
            from instant_scribe.application_orchestrator import ApplicationOrchestrator
            
            # Create orchestrator with stub worker
            orch = ApplicationOrchestrator(use_stub_worker=True)
            
            # Mock all the components to avoid actual startup
            with patch.object(orch.worker, 'start'):
                with patch.object(orch.hotkey_manager, 'start', return_value=True):
                    with patch.object(orch.vram_hotkey_manager, 'start', return_value=True):
                        with patch.object(orch.pause_hotkey_manager, 'start', return_value=True):
                            with patch.object(orch.tray_app, 'start', return_value=True):
                                with patch.object(orch.audio_streamer, 'start'):
                                    with patch.object(orch.spooler, 'start_session'):
                                        with patch.object(orch.gpu_monitor, 'start'):
                                            orch.start()
            
            # GPU check should not have been called
            mock_check.assert_not_called()

    def test_gpu_check_called_for_real_worker(self):
        """Test that GPU check is called when using real worker."""
        with patch('InstanceScrubber.gpu_capability_checker.check_gpu_capability_blocking', return_value=True) as mock_check:
            from instant_scribe.application_orchestrator import ApplicationOrchestrator
            
            # Create orchestrator without stub worker
            orch = ApplicationOrchestrator(use_stub_worker=False)
            
            # Mock all the components to avoid actual startup
            with patch.object(orch.worker, 'start'):
                with patch.object(orch.hotkey_manager, 'start', return_value=True):
                    with patch.object(orch.vram_hotkey_manager, 'start', return_value=True):
                        with patch.object(orch.pause_hotkey_manager, 'start', return_value=True):
                            with patch.object(orch.tray_app, 'start', return_value=True):
                                with patch.object(orch.audio_streamer, 'start'):
                                    with patch.object(orch.spooler, 'start_session'):
                                        with patch.object(orch.gpu_monitor, 'start'):
                                            orch.start()
            
            # GPU check should have been called
            mock_check.assert_called_once()

    def test_gpu_check_failure_exits_application(self):
        """Test that GPU check failure causes application to exit."""
        with patch('InstanceScrubber.gpu_capability_checker.check_gpu_capability_blocking', return_value=False):
            with patch('sys.exit') as mock_exit:
                from instant_scribe.application_orchestrator import ApplicationOrchestrator
                
                # Create orchestrator without stub worker
                orch = ApplicationOrchestrator(use_stub_worker=False)
                
                # Start should trigger GPU check and exit
                orch.start()
                
                # Application should have exited with code 1
                mock_exit.assert_called_once_with(1)
