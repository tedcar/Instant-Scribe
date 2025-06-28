"""Comprehensive tests for Task 57 - Model Integrity Verification.

This test suite validates the model integrity verification functionality including:
- SHA-256 checksum calculation and verification
- Model manifest generation and storage
- Offline integrity checking without internet connectivity
- Startup validation and error handling
"""

import pytest
import json
import tempfile
import hashlib
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from InstanceScrubber.model_integrity import (
    ModelIntegrityChecker,
    ModelManifest,
    ModelFileInfo,
    verify_model_integrity
)


class TestModelFileInfo:
    """Test ModelFileInfo dataclass."""
    
    def test_model_file_info_creation(self):
        """Test ModelFileInfo creation."""
        file_info = ModelFileInfo(
            path="/path/to/model.nemo",
            size_bytes=1024000,
            sha256="abc123def456",
            last_modified=1640995200.0
        )
        
        assert file_info.path == "/path/to/model.nemo"
        assert file_info.size_bytes == 1024000
        assert file_info.sha256 == "abc123def456"
        assert file_info.last_modified == 1640995200.0


class TestModelManifest:
    """Test ModelManifest dataclass."""
    
    def test_model_manifest_creation(self):
        """Test ModelManifest creation."""
        file_info = ModelFileInfo(
            path="/path/to/model.nemo",
            size_bytes=1024000,
            sha256="abc123def456",
            last_modified=1640995200.0
        )
        
        manifest = ModelManifest(
            model_name="nvidia/parakeet-tdt-0.6b-v2",
            model_version="0.6b-v2",
            huggingface_url="https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2",
            verification_date="2024-01-01 12:00:00 UTC",
            files=[file_info],
            total_size_bytes=1024000
        )
        
        assert manifest.model_name == "nvidia/parakeet-tdt-0.6b-v2"
        assert manifest.model_version == "0.6b-v2"
        assert len(manifest.files) == 1
        assert manifest.total_size_bytes == 1024000
        assert manifest.manifest_version == "1.0"


class TestModelIntegrityChecker:
    """Test ModelIntegrityChecker functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_model_files(self, temp_dir):
        """Create sample model files for testing."""
        model_dir = temp_dir / "parakeet-tdt-0.6b-v2"
        model_dir.mkdir(parents=True)
        
        # Create sample files
        files = {
            "model.nemo": b"fake model data" * 1000,
            "config.yaml": b"model_config: test",
            "tokenizer.model": b"tokenizer data" * 500,
        }
        
        created_files = []
        for filename, content in files.items():
            file_path = model_dir / filename
            file_path.write_bytes(content)
            created_files.append(file_path)
        
        return created_files
    
    def test_checker_initialization(self):
        """Test ModelIntegrityChecker initialization."""
        checker = ModelIntegrityChecker()
        assert checker.model_name == "nvidia/parakeet-tdt-0.6b-v2"
        
        custom_checker = ModelIntegrityChecker("custom/model")
        assert custom_checker.model_name == "custom/model"
    
    def test_calculate_file_sha256(self, temp_dir):
        """Test SHA-256 calculation."""
        checker = ModelIntegrityChecker()
        
        # Create test file
        test_file = temp_dir / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)
        
        # Calculate expected hash
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        # Test calculation
        calculated_hash = checker._calculate_file_sha256(test_file)
        assert calculated_hash == expected_hash
    
    def test_find_model_files(self, temp_dir, sample_model_files):
        """Test finding model files."""
        checker = ModelIntegrityChecker()
        
        # Mock the cache paths to return our temp directory
        with patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            found_files = checker._find_model_files()
            
            # Should find all sample files
            assert len(found_files) == len(sample_model_files)
            
            # Check that all files are found
            found_names = {f.name for f in found_files}
            expected_names = {f.name for f in sample_model_files}
            assert found_names == expected_names
    
    def test_generate_manifest(self, temp_dir, sample_model_files):
        """Test manifest generation."""
        checker = ModelIntegrityChecker()
        
        with patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            manifest = checker.generate_manifest()
            
            assert manifest.model_name == "nvidia/parakeet-tdt-0.6b-v2"
            assert manifest.model_version == "0.6b-v2"
            assert len(manifest.files) == len(sample_model_files)
            assert manifest.total_size_bytes > 0
            
            # Verify file info
            for file_info in manifest.files:
                file_path = Path(file_info.path)
                assert file_path.exists()
                assert file_info.size_bytes == file_path.stat().st_size
                assert len(file_info.sha256) == 64  # SHA-256 hex length
    
    def test_save_and_load_manifest(self, temp_dir, sample_model_files):
        """Test saving and loading manifest."""
        checker = ModelIntegrityChecker()
        
        # Mock manifest path
        manifest_path = temp_dir / "model_manifest.json"
        with patch.object(checker, '_get_manifest_path', return_value=manifest_path), \
             patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            
            # Generate and save manifest
            original_manifest = checker.generate_manifest()
            saved_path = checker.save_manifest(original_manifest)
            
            assert saved_path == manifest_path
            assert manifest_path.exists()
            
            # Load manifest
            loaded_manifest = checker.load_manifest()
            
            assert loaded_manifest is not None
            assert loaded_manifest.model_name == original_manifest.model_name
            assert len(loaded_manifest.files) == len(original_manifest.files)
            
            # Compare file info
            for orig, loaded in zip(original_manifest.files, loaded_manifest.files):
                assert orig.path == loaded.path
                assert orig.size_bytes == loaded.size_bytes
                assert orig.sha256 == loaded.sha256
    
    def test_verify_model_integrity_success(self, temp_dir, sample_model_files):
        """Test successful model integrity verification."""
        checker = ModelIntegrityChecker()
        
        with patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            # Generate manifest
            manifest = checker.generate_manifest()
            
            # Verify integrity (should pass)
            result = checker.verify_model_integrity(manifest)
            assert result is True
    
    def test_verify_model_integrity_missing_file(self, temp_dir, sample_model_files):
        """Test integrity verification with missing file."""
        checker = ModelIntegrityChecker()
        
        with patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            # Generate manifest
            manifest = checker.generate_manifest()
            
            # Remove one file
            sample_model_files[0].unlink()
            
            # Verify integrity (should fail)
            result = checker.verify_model_integrity(manifest)
            assert result is False
    
    def test_verify_model_integrity_corrupted_file(self, temp_dir, sample_model_files):
        """Test integrity verification with corrupted file."""
        checker = ModelIntegrityChecker()
        
        with patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            # Generate manifest
            manifest = checker.generate_manifest()
            
            # Corrupt one file
            sample_model_files[0].write_bytes(b"corrupted data")
            
            # Verify integrity (should fail)
            result = checker.verify_model_integrity(manifest)
            assert result is False
    
    def test_ensure_model_integrity_new_manifest(self, temp_dir, sample_model_files):
        """Test ensuring integrity with new manifest generation."""
        checker = ModelIntegrityChecker()
        
        manifest_path = temp_dir / "model_manifest.json"
        with patch.object(checker, '_get_manifest_path', return_value=manifest_path), \
             patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            
            # Ensure integrity (should generate new manifest)
            result = checker.ensure_model_integrity()
            assert result is True
            assert manifest_path.exists()
    
    def test_ensure_model_integrity_existing_manifest(self, temp_dir, sample_model_files):
        """Test ensuring integrity with existing manifest."""
        checker = ModelIntegrityChecker()
        
        manifest_path = temp_dir / "model_manifest.json"
        with patch.object(checker, '_get_manifest_path', return_value=manifest_path), \
             patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            
            # Generate and save manifest first
            manifest = checker.generate_manifest()
            checker.save_manifest(manifest)
            
            # Ensure integrity (should verify existing manifest)
            result = checker.ensure_model_integrity()
            assert result is True
    
    def test_no_model_files_found(self, temp_dir):
        """Test behavior when no model files are found."""
        checker = ModelIntegrityChecker()
        
        # Empty directory
        with patch.object(checker, '_get_model_cache_paths', return_value=[temp_dir]):
            with pytest.raises(FileNotFoundError, match="No model files found"):
                checker.generate_manifest()
    
    def test_load_nonexistent_manifest(self, temp_dir):
        """Test loading non-existent manifest."""
        checker = ModelIntegrityChecker()
        
        manifest_path = temp_dir / "nonexistent.json"
        with patch.object(checker, '_get_manifest_path', return_value=manifest_path):
            manifest = checker.load_manifest()
            assert manifest is None
    
    def test_load_corrupted_manifest(self, temp_dir):
        """Test loading corrupted manifest file."""
        checker = ModelIntegrityChecker()
        
        manifest_path = temp_dir / "corrupted.json"
        manifest_path.write_text("invalid json content")
        
        with patch.object(checker, '_get_manifest_path', return_value=manifest_path):
            manifest = checker.load_manifest()
            assert manifest is None


class TestConvenienceFunction:
    """Test the convenience function."""
    
    def test_verify_model_integrity_function(self):
        """Test the verify_model_integrity convenience function."""
        with patch('InstanceScrubber.model_integrity.ModelIntegrityChecker') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.ensure_model_integrity.return_value = True
            mock_checker_class.return_value = mock_checker
            
            result = verify_model_integrity("test/model", generate_if_missing=True)
            
            assert result is True
            mock_checker_class.assert_called_once_with("test/model")
            mock_checker.ensure_model_integrity.assert_called_once()
    
    def test_verify_model_integrity_no_generation(self):
        """Test convenience function without manifest generation."""
        with patch('InstanceScrubber.model_integrity.ModelIntegrityChecker') as mock_checker_class:
            mock_checker = Mock()
            mock_manifest = Mock()
            mock_checker.load_manifest.return_value = mock_manifest
            mock_checker.verify_model_integrity.return_value = True
            mock_checker_class.return_value = mock_checker
            
            result = verify_model_integrity("test/model", generate_if_missing=False)
            
            assert result is True
            mock_checker.load_manifest.assert_called_once()
            mock_checker.verify_model_integrity.assert_called_once_with(mock_manifest)


class TestIntegration:
    """Integration tests for complete workflow."""
    
    def test_complete_workflow(self, tmp_path):
        """Test complete integrity verification workflow."""
        # Create mock model structure
        model_dir = tmp_path / "cache" / "parakeet-model"
        model_dir.mkdir(parents=True)
        
        # Create model files
        model_file = model_dir / "model.nemo"
        config_file = model_dir / "config.yaml"
        
        model_file.write_bytes(b"model data" * 1000)
        config_file.write_bytes(b"config: test")
        
        checker = ModelIntegrityChecker("test/model")
        
        with patch.object(checker, '_get_model_cache_paths', return_value=[tmp_path / "cache"]):
            # 1. Generate manifest
            manifest = checker.generate_manifest()
            assert len(manifest.files) == 2
            
            # 2. Save manifest
            manifest_path = tmp_path / "manifest.json"
            with patch.object(checker, '_get_manifest_path', return_value=manifest_path):
                saved_path = checker.save_manifest(manifest)
                assert saved_path.exists()
                
                # 3. Load and verify
                loaded_manifest = checker.load_manifest()
                assert loaded_manifest is not None
                
                verification_result = checker.verify_model_integrity(loaded_manifest)
                assert verification_result is True
                
                # 4. Test corruption detection
                model_file.write_bytes(b"corrupted")
                verification_result = checker.verify_model_integrity(loaded_manifest)
                assert verification_result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
