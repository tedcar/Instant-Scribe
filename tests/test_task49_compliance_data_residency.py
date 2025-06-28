"""Tests for Task 49: Compliance & Data Residency

Tests both archive directory relocation (49.1) and GDPR data export (49.2).
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from InstanceScrubber.config_manager import ConfigManager
from InstanceScrubber.archive_manager import ArchiveManager


class TestArchiveDirectoryRelocation:
    """Test Task 49.1: Archive directory relocation functionality."""

    def test_set_archive_directory_valid_path(self, tmp_path):
        """Test setting a valid archive directory."""
        config = ConfigManager()
        new_archive_path = tmp_path / "custom_archive"
        
        # Should succeed and create the directory
        result = config.set_archive_directory(str(new_archive_path))
        assert result is True
        assert config.get("archive_root") == str(new_archive_path)
        assert new_archive_path.exists()
        assert new_archive_path.is_dir()

    def test_set_archive_directory_with_env_vars(self, tmp_path):
        """Test setting archive directory with environment variables."""
        config = ConfigManager()
        
        # Set a test environment variable
        test_env_var = "TEST_ARCHIVE_BASE"
        os.environ[test_env_var] = str(tmp_path)
        
        try:
            new_archive_path = f"%{test_env_var}%/custom_archive"
            result = config.set_archive_directory(new_archive_path)
            assert result is True
            assert config.get("archive_root") == new_archive_path
            
            # Verify the actual directory was created
            expected_path = tmp_path / "custom_archive"
            assert expected_path.exists()
        finally:
            del os.environ[test_env_var]

    def test_set_archive_directory_invalid_path(self):
        """Test setting an invalid archive directory."""
        config = ConfigManager()
        
        # Try to set a path that cannot be created (invalid characters on Windows)
        if os.name == "nt":
            invalid_path = "C:\\invalid<>path"
        else:
            invalid_path = "/root/no_permission"
        
        with pytest.raises(ValueError, match="Cannot create or access directory"):
            config.set_archive_directory(invalid_path)

    def test_set_archive_directory_no_write_permission(self, tmp_path):
        """Test setting archive directory without write permission."""
        config = ConfigManager()
        
        # Create a directory and remove write permissions
        no_write_dir = tmp_path / "no_write"
        no_write_dir.mkdir()
        
        # Make directory read-only (this test may not work on all systems)
        try:
            no_write_dir.chmod(0o444)
            with pytest.raises(ValueError, match="No write permission"):
                config.set_archive_directory(str(no_write_dir))
        finally:
            # Restore permissions for cleanup
            no_write_dir.chmod(0o755)

    def test_archive_manager_uses_custom_directory(self, tmp_path):
        """Test that ArchiveManager respects custom archive directory."""
        config = ConfigManager()
        custom_archive = tmp_path / "custom_archive"
        config.set_archive_directory(str(custom_archive))
        
        # Create ArchiveManager with the config
        archive_manager = ArchiveManager(config_manager=config)
        assert archive_manager.base_dir == custom_archive.resolve()

    def test_archive_manager_creates_session_in_custom_directory(self, tmp_path):
        """Test that sessions are created in the custom directory."""
        config = ConfigManager()
        custom_archive = tmp_path / "custom_archive"
        config.set_archive_directory(str(custom_archive))
        
        # Create a test WAV file
        test_wav = tmp_path / "test.wav"
        test_wav.write_bytes(b"fake wav data")
        
        # Archive a session
        archive_manager = ArchiveManager(config_manager=config)
        session_dir = archive_manager.archive(
            wav_path=test_wav,
            transcription="This is a test transcription"
        )
        
        # Verify session was created in custom directory
        assert session_dir.parent == custom_archive
        assert (session_dir / "recording.wav").exists()
        assert any(f.suffix == ".txt" for f in session_dir.iterdir())


class TestGDPRDataExport:
    """Test Task 49.2: GDPR data export functionality."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock config with test data."""
        config = MagicMock()
        config.get.return_value = str(tmp_path / "archive")
        config._config_path = tmp_path / "config.json"
        config.settings = {
            "hotkey": "ctrl+alt+f",
            "archive_root": str(tmp_path / "archive"),
            "show_notifications": True,
        }
        return config

    @pytest.fixture
    def sample_data_structure(self, tmp_path):
        """Create sample data structure for testing."""
        # Create archive directory with sample sessions
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        
        session1 = archive_dir / "1_2024-01-01_12-00-00"
        session1.mkdir()
        (session1 / "recording.wav").write_bytes(b"fake wav data 1")
        (session1 / "transcription.txt").write_text("Hello world")
        
        session2 = archive_dir / "2_2024-01-02_13-00-00"
        session2.mkdir()
        (session2 / "recording.wav").write_bytes(b"fake wav data 2")
        (session2 / "test_transcription.txt").write_text("Test transcription")
        
        # Create config file
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"hotkey": "ctrl+alt+f"}))
        
        # Create logs directory
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "app.log").write_text("Sample log content")
        
        # Create temp directory
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / "chunk_0001.pcm").write_bytes(b"audio chunk data")
        
        return {
            "archive": archive_dir,
            "config": config_file,
            "logs": logs_dir,
            "temp": temp_dir,
        }

    def test_gdpr_export_basic_functionality(self, tmp_path, sample_data_structure):
        """Test basic GDPR export functionality."""
        # Import here to avoid issues with module loading
        from scripts.gdpr_export import GDPRExporter
        
        with patch('scripts.gdpr_export.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config.get.return_value = str(sample_data_structure["archive"])
            mock_config._config_path = sample_data_structure["config"]
            mock_config.settings = {"hotkey": "ctrl+alt+f"}
            mock_config_class.return_value = mock_config
            
            exporter = GDPRExporter(output_dir=tmp_path)
            
            # Mock the directory getters to return our test data
            exporter._get_archive_directory = lambda: sample_data_structure["archive"]
            exporter._get_logs_directory = lambda: sample_data_structure["logs"]
            exporter._get_spooler_temp_directory = lambda: sample_data_structure["temp"]
            
            export_path = exporter.export_all_data()
            
            # Verify export file was created
            assert export_path.exists()
            assert export_path.suffix == ".zip"
            assert "gdpr_export" in export_path.name

    def test_gdpr_export_zip_contents(self, tmp_path, sample_data_structure):
        """Test that the exported ZIP contains expected files."""
        from scripts.gdpr_export import GDPRExporter
        
        with patch('scripts.gdpr_export.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config.get.return_value = str(sample_data_structure["archive"])
            mock_config._config_path = sample_data_structure["config"]
            mock_config.settings = {"hotkey": "ctrl+alt+f"}
            mock_config_class.return_value = mock_config
            
            exporter = GDPRExporter(output_dir=tmp_path, include_logs=True)
            
            # Mock the directory getters
            exporter._get_archive_directory = lambda: sample_data_structure["archive"]
            exporter._get_logs_directory = lambda: sample_data_structure["logs"]
            exporter._get_spooler_temp_directory = lambda: sample_data_structure["temp"]
            
            export_path = exporter.export_all_data()
            
            # Extract and verify ZIP contents
            with zipfile.ZipFile(export_path, 'r') as zipf:
                file_list = zipf.namelist()
                
                # Check for expected directories and files
                assert any("archived_recordings/" in f for f in file_list)
                assert any("configuration/" in f for f in file_list)
                assert any("temporary_files/" in f for f in file_list)
                assert any("logs/" in f for f in file_list)
                assert "export_metadata.json" in file_list
                assert "README.txt" in file_list
                
                # Check specific files
                assert any("1_2024-01-01_12-00-00/recording.wav" in f for f in file_list)
                assert any("config.json" in f for f in file_list)
                assert any("app.log" in f for f in file_list)
                assert any("chunk_0001.pcm" in f for f in file_list)

    def test_gdpr_export_metadata_generation(self, tmp_path, sample_data_structure):
        """Test that export metadata is correctly generated."""
        from scripts.gdpr_export import GDPRExporter
        
        with patch('scripts.gdpr_export.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config.get.return_value = str(sample_data_structure["archive"])
            mock_config._config_path = sample_data_structure["config"]
            mock_config.settings = {"hotkey": "ctrl+alt+f"}
            mock_config_class.return_value = mock_config
            
            exporter = GDPRExporter(output_dir=tmp_path)
            
            # Mock the directory getters
            exporter._get_archive_directory = lambda: sample_data_structure["archive"]
            exporter._get_logs_directory = lambda: sample_data_structure["logs"]
            exporter._get_spooler_temp_directory = lambda: sample_data_structure["temp"]
            
            export_path = exporter.export_all_data()
            
            # Extract and check metadata
            with zipfile.ZipFile(export_path, 'r') as zipf:
                metadata_content = zipf.read("export_metadata.json").decode('utf-8')
                metadata = json.loads(metadata_content)
                
                assert "export_timestamp" in metadata
                assert "instant_scribe_version" in metadata
                assert "exported_data_types" in metadata
                assert "file_counts" in metadata
                assert "total_size_bytes" in metadata
                
                # Check that data types were recorded
                assert "archived_recordings" in metadata["exported_data_types"]
                assert "configuration" in metadata["exported_data_types"]
                assert "temporary_files" in metadata["exported_data_types"]

    def test_gdpr_export_config_sanitization(self, tmp_path):
        """Test that sensitive config data is sanitized."""
        from scripts.gdpr_export import GDPRExporter
        
        exporter = GDPRExporter(output_dir=tmp_path)
        
        # Test config with sensitive data
        test_config = {
            "hotkey": "ctrl+alt+f",
            "api_key": "secret123",
            "user_token": "token456",
            "password": "mypassword",
            "normal_setting": "value",
        }
        
        sanitized = exporter._sanitize_config(test_config)
        
        assert sanitized["hotkey"] == "ctrl+alt+f"
        assert sanitized["normal_setting"] == "value"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["user_token"] == "[REDACTED]"
        assert sanitized["password"] == "[REDACTED]"

    def test_gdpr_export_no_data_scenario(self, tmp_path):
        """Test GDPR export when no user data exists."""
        from scripts.gdpr_export import GDPRExporter
        
        with patch('scripts.gdpr_export.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config.get.return_value = str(tmp_path / "nonexistent")
            mock_config._config_path = tmp_path / "config.json"
            mock_config.settings = {"hotkey": "ctrl+alt+f"}
            mock_config_class.return_value = mock_config
            
            # Create minimal config file
            (tmp_path / "config.json").write_text(json.dumps({"hotkey": "ctrl+alt+f"}))
            
            exporter = GDPRExporter(output_dir=tmp_path)
            export_path = exporter.export_all_data()
            
            # Should still create export with metadata
            assert export_path.exists()
            
            with zipfile.ZipFile(export_path, 'r') as zipf:
                file_list = zipf.namelist()
                assert "export_metadata.json" in file_list
                assert "README.txt" in file_list
                assert any("configuration/" in f for f in file_list)


def test_task49_integration(tmp_path):
    """Integration test for Task 49: Archive relocation + GDPR export."""
    # Test the complete workflow
    config = ConfigManager()
    
    # 1. Set custom archive directory
    custom_archive = tmp_path / "my_custom_archive"
    config.set_archive_directory(str(custom_archive))
    
    # 2. Create some archived data
    archive_manager = ArchiveManager(config_manager=config)
    test_wav = tmp_path / "test.wav"
    test_wav.write_bytes(b"fake wav data")
    
    session_dir = archive_manager.archive(
        wav_path=test_wav,
        transcription="Integration test transcription"
    )
    
    # 3. Export data via GDPR script
    from scripts.gdpr_export import GDPRExporter
    
    with patch('scripts.gdpr_export.ConfigManager') as mock_config_class:
        mock_config_class.return_value = config
        
        exporter = GDPRExporter(output_dir=tmp_path)
        export_path = exporter.export_all_data()
        
        # 4. Verify export contains our custom archive data
        assert export_path.exists()
        
        with zipfile.ZipFile(export_path, 'r') as zipf:
            file_list = zipf.namelist()
            
            # Should contain our session data
            assert any("archived_recordings/" in f for f in file_list)
            assert any("recording.wav" in f for f in file_list)
            assert any(".txt" in f for f in file_list)
