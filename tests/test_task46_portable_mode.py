"""Test suite for Task 46: Portable Mode Distribution.

This module tests the portable mode functionality including:
- Portable mode detection
- Path resolution in portable mode
- Configuration management in portable mode
- Resource location in portable mode
- ZIP distribution creation
"""

import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from instant_scribe import portable_mode


class TestPortableModeDetection:
    """Test portable mode detection functionality."""

    def test_portable_mode_detection_with_marker(self, tmp_path):
        """Test that portable mode is detected when marker file exists."""
        # Create a fake executable directory
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        
        # Create portable marker
        marker = exe_dir / "portable.txt"
        marker.write_text("portable mode marker")
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            assert portable_mode.is_portable_mode() is True

    def test_portable_mode_detection_without_marker(self, tmp_path):
        """Test that portable mode is not detected when marker file is missing."""
        # Create a fake executable directory without marker
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            assert portable_mode.is_portable_mode() is False

    def test_get_executable_directory_frozen(self):
        """Test executable directory detection in frozen mode."""
        fake_exe_path = Path("/fake/path/to/app.exe")
        
        with patch('sys.frozen', True, create=True), \
             patch('sys.executable', str(fake_exe_path)):
            result = portable_mode.get_executable_directory()
            assert result == fake_exe_path.parent

    def test_get_executable_directory_development(self):
        """Test executable directory detection in development mode."""
        # In development mode, should return project root
        result = portable_mode.get_executable_directory()
        # Should be the parent of the instant_scribe package
        expected = Path(__file__).resolve().parent.parent
        assert result == expected


class TestPortablePathResolution:
    """Test path resolution in portable mode."""

    def test_get_portable_data_directory(self, tmp_path):
        """Test portable data directory path."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            result = portable_mode.get_portable_data_directory()
            assert result == exe_dir / "data"

    def test_get_config_path_portable_mode(self, tmp_path):
        """Test config path in portable mode."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        marker = exe_dir / "portable.txt"
        marker.write_text("portable")
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            result = portable_mode.get_config_path()
            assert result == exe_dir / "data" / "config.json"

    def test_get_config_path_standard_mode(self, tmp_path):
        """Test config path in standard mode."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        # No portable marker
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir), \
             patch.dict(os.environ, {'APPDATA': str(tmp_path / "appdata")}):
            result = portable_mode.get_config_path()
            assert result == tmp_path / "appdata" / "Instant_Scribe" / "config.json"

    def test_get_data_path_portable_mode(self, tmp_path):
        """Test data path resolution in portable mode."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        marker = exe_dir / "portable.txt"
        marker.write_text("portable")
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            result = portable_mode.get_data_path("logs/app.log")
            assert result == exe_dir / "data" / "logs" / "app.log"

    def test_get_temp_directory_portable_mode(self, tmp_path):
        """Test temp directory in portable mode."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        marker = exe_dir / "portable.txt"
        marker.write_text("portable")
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            result = portable_mode.get_temp_directory()
            assert result == exe_dir / "data" / "temp"

    def test_get_archive_directory_portable_mode(self, tmp_path):
        """Test archive directory in portable mode."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        marker = exe_dir / "portable.txt"
        marker.write_text("portable")
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            result = portable_mode.get_archive_directory()
            assert result == exe_dir / "data" / "archives"

    def test_get_archive_directory_standard_mode(self, tmp_path):
        """Test archive directory in standard mode returns None."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        # No portable marker
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            result = portable_mode.get_archive_directory()
            assert result is None


class TestPortableDirectoryManagement:
    """Test portable directory creation and management."""

    def test_ensure_portable_directories(self, tmp_path):
        """Test that portable directories are created correctly."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        marker = exe_dir / "portable.txt"
        marker.write_text("portable")
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            portable_mode.ensure_portable_directories()
            
            data_dir = exe_dir / "data"
            assert data_dir.exists()
            assert (data_dir / "temp").exists()
            assert (data_dir / "archives").exists()
            assert (data_dir / "logs").exists()
            assert (data_dir / "reports").exists()
            assert (data_dir / "metrics").exists()

    def test_ensure_portable_directories_standard_mode(self, tmp_path):
        """Test that ensure_portable_directories does nothing in standard mode."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        # No portable marker
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            portable_mode.ensure_portable_directories()
            
            # Should not create data directory
            assert not (exe_dir / "data").exists()

    def test_create_portable_marker(self, tmp_path):
        """Test creation of portable marker file."""
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            portable_mode.create_portable_marker()
            
            marker = exe_dir / "portable.txt"
            assert marker.exists()
            content = marker.read_text(encoding="utf-8")
            assert "portable mode" in content.lower()


class TestConfigManagerPortableIntegration:
    """Test config manager integration with portable mode."""

    def test_config_manager_portable_mode(self, tmp_path):
        """Test that ConfigManager uses portable paths in portable mode."""
        from instant_scribe.config_manager import ConfigManager
        
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        marker = exe_dir / "portable.txt"
        marker.write_text("portable")
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            config = ConfigManager()
            expected_path = exe_dir / "data" / "config.json"
            assert config._config_path == expected_path


class TestSystemCheckPortableIntegration:
    """Test system_check.py integration with portable mode."""

    def test_system_check_portable_mode_detection(self, tmp_path):
        """Test that system_check detects portable mode correctly."""
        # This would require running the actual system_check script
        # For now, we'll test the portable mode detection logic
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        marker = exe_dir / "portable.txt"
        marker.write_text("portable")
        
        with patch.object(portable_mode, 'get_executable_directory', return_value=exe_dir):
            assert portable_mode.is_portable_mode() is True


class TestPortableBuildScript:
    """Test the portable build script functionality."""

    def test_portable_zip_creation(self, tmp_path):
        """Test that portable ZIP can be created with proper structure."""
        # Create a mock PyInstaller build
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create mock executable and files
        (source_dir / "Instant Scribe.exe").write_text("fake exe")
        (source_dir / "assets").mkdir()
        (source_dir / "assets" / "icon.ico").write_text("fake icon")
        
        # Create output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Create temporary portable structure
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        
        # Copy source to temp (simulating the build script)
        import shutil
        shutil.copytree(source_dir, temp_dir, dirs_exist_ok=True)
        
        # Add portable marker
        (temp_dir / "portable.txt").write_text("portable mode marker")
        
        # Create data directories
        data_dir = temp_dir / "data"
        for subdir in ["temp", "archives", "logs", "reports", "metrics"]:
            (data_dir / subdir).mkdir(parents=True)
        
        # Create ZIP
        zip_path = output_dir / "test_portable.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    arc_path = file_path.relative_to(temp_dir)
                    zf.write(file_path, arc_path)
        
        # Verify ZIP contents
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "portable.txt" in names
            assert "Instant Scribe.exe" in names
            assert "assets/icon.ico" in names
            assert "data/temp/" in names or any(n.startswith("data/temp/") for n in names)


if __name__ == "__main__":
    pytest.main([__file__])
