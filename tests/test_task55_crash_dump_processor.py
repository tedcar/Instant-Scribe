"""Tests for Task 55: Crash Dump Processor

Tests both minidump generation (55.1) and PowerShell dump decoder (55.2).
"""

from __future__ import annotations

import faulthandler
import os
import sys
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from instant_scribe import crash_reporter


class TestMinidumpGeneration:
    """Test minidump generation functionality."""

    def test_faulthandler_available(self):
        """Test that faulthandler is available."""
        assert hasattr(faulthandler, 'enable')
        assert hasattr(faulthandler, 'dump_traceback')

    def test_generate_minidump_function_exists(self):
        """Test that generate_minidump function is available."""
        assert hasattr(crash_reporter, 'generate_minidump')
        assert callable(crash_reporter.generate_minidump)

    def test_generate_minidump_with_custom_filename(self):
        """Test minidump generation with custom filename."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the minidump directory
            with patch.object(crash_reporter, '_MINIDUMP_DIR', Path(temp_dir)):
                with patch.object(crash_reporter, '_ENABLE_MINIDUMPS', True):
                    # Generate minidump
                    result = crash_reporter.generate_minidump("test_dump.dmp")
                    
                    assert result is not None
                    assert result.name == "test_dump.dmp"
                    assert result.exists()
                    assert result.stat().st_size > 0

    def test_generate_minidump_with_auto_filename(self):
        """Test minidump generation with automatic filename."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(crash_reporter, '_MINIDUMP_DIR', Path(temp_dir)):
                with patch.object(crash_reporter, '_ENABLE_MINIDUMPS', True):
                    # Generate minidump
                    result = crash_reporter.generate_minidump()
                    
                    assert result is not None
                    assert result.name.startswith("crash_dump_")
                    assert result.name.endswith(".dmp")
                    assert result.exists()

    def test_generate_minidump_disabled(self):
        """Test that minidump generation returns None when disabled."""
        with patch.object(crash_reporter, '_ENABLE_MINIDUMPS', False):
            result = crash_reporter.generate_minidump()
            assert result is None

    def test_crash_reporter_install_enables_faulthandler(self):
        """Test that crash reporter installation enables faulthandler."""
        with patch.object(faulthandler, 'enable') as mock_enable:
            with patch.object(crash_reporter, '_ENABLE_MINIDUMPS', True):
                with patch.object(crash_reporter, '_installed', False):
                    crash_reporter.install()
                    mock_enable.assert_called_once()

    def test_exception_handler_generates_minidump(self):
        """Test that exception handler generates minidump."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(crash_reporter, '_MINIDUMP_DIR', Path(temp_dir)):
                with patch.object(crash_reporter, '_ENABLE_MINIDUMPS', True):
                    with patch.object(crash_reporter, 'generate_report_zip'):
                        # Simulate exception
                        try:
                            raise ValueError("Test exception")
                        except ValueError as exc:
                            crash_reporter._handle_exception(
                                type(exc), exc, exc.__traceback__
                            )
                        
                        # Check that minidump was created
                        minidump_files = list(Path(temp_dir).glob("*.dmp"))
                        assert len(minidump_files) > 0


class TestReportZipWithMinidumps:
    """Test report ZIP generation with minidumps."""

    def test_generate_report_zip_includes_minidump(self):
        """Test that report ZIP includes minidumps."""
        import zipfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock crash log
            crash_log = Path(temp_dir) / "crash.log"
            crash_log.write_text("Test crash log")
            
            # Create mock minidump
            minidump_dir = Path(temp_dir) / "minidumps"
            minidump_dir.mkdir()
            minidump_file = minidump_dir / "test_dump.dmp"
            minidump_file.write_text("Test minidump content")
            
            # Create reports directory
            reports_dir = Path(temp_dir) / "reports"
            reports_dir.mkdir()
            
            with patch.object(crash_reporter, '_LOG_PATH', crash_log):
                with patch.object(crash_reporter, '_MINIDUMP_DIR', minidump_dir):
                    with patch.object(crash_reporter, '_REPORTS_DIR', reports_dir):
                        # Generate report ZIP
                        zip_path = crash_reporter.generate_report_zip()
                        
                        assert zip_path.exists()
                        
                        # Check ZIP contents
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            names = zf.namelist()
                            assert "crash.log" in names
                            assert any(name.startswith("minidump/") for name in names)

    def test_generate_report_zip_without_minidumps(self):
        """Test that report ZIP works even without minidumps."""
        import zipfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock crash log
            crash_log = Path(temp_dir) / "crash.log"
            crash_log.write_text("Test crash log")
            
            # No minidump directory
            minidump_dir = Path(temp_dir) / "minidumps"
            
            # Create reports directory
            reports_dir = Path(temp_dir) / "reports"
            reports_dir.mkdir()
            
            with patch.object(crash_reporter, '_LOG_PATH', crash_log):
                with patch.object(crash_reporter, '_MINIDUMP_DIR', minidump_dir):
                    with patch.object(crash_reporter, '_REPORTS_DIR', reports_dir):
                        # Generate report ZIP
                        zip_path = crash_reporter.generate_report_zip()
                        
                        assert zip_path.exists()
                        
                        # Check ZIP contents
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            names = zf.namelist()
                            assert "crash.log" in names
                            # Should not have minidump files
                            assert not any(name.startswith("minidump/") for name in names)


class TestPowerShellDumpDecoder:
    """Test PowerShell dump decoder functionality."""

    def test_dump_decoder_script_exists(self):
        """Test that dump decoder script exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "dump_decoder.ps1"
        assert script_path.exists()

    def test_dump_decoder_help(self):
        """Test that dump decoder shows help."""
        script_path = Path(__file__).parent.parent / "scripts" / "dump_decoder.ps1"
        
        try:
            # Test PowerShell help
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-?"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Should show usage information
            assert "DumpFile" in result.stdout or "Usage" in result.stdout or result.returncode == 0
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # PowerShell not available or timeout - skip test
            pytest.skip("PowerShell not available or test timeout")

    def test_create_sample_dump_file(self):
        """Test creating a sample dump file for decoder testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            dump_file = Path(temp_dir) / "test_dump.dmp"
            
            # Create a sample Python stack trace (what faulthandler produces)
            sample_trace = """Thread 0x00001234 (most recent call first):
  File "test_script.py", line 42, in main
    raise ValueError("Test exception")
  File "test_script.py", line 50, in <module>
    main()

Thread 0x00005678:
  File "threading.py", line 890, in _bootstrap
    self._bootstrap_inner()
  File "threading.py", line 932, in _bootstrap_inner
    self.run()
"""
            
            dump_file.write_text(sample_trace, encoding='utf-8')
            assert dump_file.exists()
            assert dump_file.stat().st_size > 0
            
            # Verify content
            content = dump_file.read_text(encoding='utf-8')
            assert "Thread 0x" in content
            assert "test_script.py" in content


class TestIntegratedCrashDumpWorkflow:
    """Test integrated crash dump workflow."""

    def test_full_crash_dump_workflow(self):
        """Test complete crash dump workflow from exception to report."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up temporary directories
            log_path = Path(temp_dir) / "crash.log"
            minidump_dir = Path(temp_dir) / "minidumps"
            reports_dir = Path(temp_dir) / "reports"
            
            with patch.object(crash_reporter, '_LOG_PATH', log_path):
                with patch.object(crash_reporter, '_MINIDUMP_DIR', minidump_dir):
                    with patch.object(crash_reporter, '_REPORTS_DIR', reports_dir):
                        with patch.object(crash_reporter, '_ENABLE_MINIDUMPS', True):
                            # Reset installation state
                            crash_reporter._installed = False
                            
                            # Install crash reporter
                            crash_reporter.install()
                            
                            # Simulate crash
                            try:
                                raise RuntimeError("Test crash for dump generation")
                            except RuntimeError as exc:
                                crash_reporter._handle_exception(
                                    type(exc), exc, exc.__traceback__
                                )
                            
                            # Verify crash log exists
                            assert log_path.exists()
                            
                            # Verify minidump directory was created
                            assert minidump_dir.exists()
                            
                            # Verify report ZIP was created
                            assert reports_dir.exists()
                            zip_files = list(reports_dir.glob("*.zip"))
                            assert len(zip_files) > 0

    def test_configuration_environment_variables(self):
        """Test configuration via environment variables."""
        # Test minidump directory configuration
        with patch.dict(os.environ, {'INSTANT_SCRIBE_MINIDUMP_DIR': 'custom_dumps'}):
            # Reload the module to pick up new environment
            import importlib
            importlib.reload(crash_reporter)
            
            assert str(crash_reporter._MINIDUMP_DIR) == 'custom_dumps'
        
        # Test enable/disable minidumps
        with patch.dict(os.environ, {'INSTANT_SCRIBE_ENABLE_MINIDUMPS': 'false'}):
            importlib.reload(crash_reporter)
            assert crash_reporter._ENABLE_MINIDUMPS is False


def test_task55_integration():
    """Integration test for Task 55: Complete crash dump processor workflow."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up test environment
        log_path = Path(temp_dir) / "crash.log"
        minidump_dir = Path(temp_dir) / "minidumps"
        reports_dir = Path(temp_dir) / "reports"
        
        with patch.object(crash_reporter, '_LOG_PATH', log_path):
            with patch.object(crash_reporter, '_MINIDUMP_DIR', minidump_dir):
                with patch.object(crash_reporter, '_REPORTS_DIR', reports_dir):
                    with patch.object(crash_reporter, '_ENABLE_MINIDUMPS', True):
                        # Test 55.1: Minidump generation
                        minidump_path = crash_reporter.generate_minidump("integration_test.dmp")
                        assert minidump_path is not None
                        assert minidump_path.exists()
                        
                        # Test crash reporter integration
                        crash_reporter._installed = False
                        crash_reporter.install()
                        
                        # Simulate exception with minidump generation
                        try:
                            raise ValueError("Integration test exception")
                        except ValueError as exc:
                            crash_reporter._handle_exception(
                                type(exc), exc, exc.__traceback__
                            )
                        
                        # Verify all components work together
                        assert log_path.exists()
                        assert minidump_dir.exists()
                        
                        # Test 55.2: PowerShell script exists
                        script_path = Path(__file__).parent.parent / "scripts" / "dump_decoder.ps1"
                        assert script_path.exists()
                        
                        # Verify script has proper PowerShell syntax (basic check)
                        script_content = script_path.read_text(encoding='utf-8')
                        assert "param(" in script_content
                        assert "DumpFile" in script_content
                        assert "function" in script_content.lower()


if __name__ == "__main__":
    # Run the integration test directly
    test_task55_integration()
    print("Task 55 integration test completed successfully!")
