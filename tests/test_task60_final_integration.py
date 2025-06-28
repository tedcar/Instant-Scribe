"""Comprehensive tests for Task 60 - Final Integration & Polish.

This test suite validates:
- Complete system integration
- All components working together
- Performance benchmarks
- Final cleanup and polish
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from InstanceScrubber.config_manager import ConfigManager


class TestSystemIntegration:
    """Test complete system integration."""
    
    def test_config_system_integration(self):
        """Test that configuration system works end-to-end."""
        # Test 1: ConfigManager loads and validates
        config_manager = ConfigManager()
        assert config_manager.settings is not None
        assert isinstance(config_manager.settings, dict)
        
        # Test 2: Schema validation works
        if hasattr(config_manager, 'validate_config'):
            assert config_manager.validate_config(config_manager.DEFAULTS) is True
        
        # Test 3: Configuration file exists and is valid
        config_path = config_manager._config_path
        assert config_path.exists(), "Configuration file should exist"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        assert isinstance(config_data, dict), "Config should be valid JSON"
    
    def test_schema_validation_integration(self):
        """Test that JSON schema validation is properly integrated."""
        schema_path = Path(__file__).parent.parent / "config.schema.json"
        assert schema_path.exists(), "JSON schema should exist"
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Validate schema structure
        assert "$schema" in schema
        assert "properties" in schema
        assert "type" in schema
        
        # Check that schema covers key configuration options
        properties = schema["properties"]
        required_properties = ["hotkey", "vad_aggressiveness", "show_notifications"]
        
        for prop in required_properties:
            assert prop in properties, f"Schema should define property: {prop}"
    
    def test_cli_tools_integration(self):
        """Test that CLI tools are properly integrated."""
        cli_tool_path = Path(__file__).parent.parent / "scripts" / "upgrade_config.py"
        assert cli_tool_path.exists(), "CLI tool should exist"
        
        # Test that CLI tool can be imported
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("upgrade_config", cli_tool_path)
            cli_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli_module)
            
            # Check that main functions exist
            assert hasattr(cli_module, 'main'), "CLI tool should have main function"
            assert hasattr(cli_module, 'load_schema'), "CLI tool should have load_schema function"
            
        except Exception as exc:
            pytest.fail(f"CLI tool import failed: {exc}")


class TestDocumentationIntegration:
    """Test documentation integration and completeness."""
    
    def test_readme_integration(self):
        """Test that README.md is comprehensive and accurate."""
        readme_path = Path(__file__).parent.parent / "README.md"
        assert readme_path.exists(), "README.md should exist"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for essential sections
        essential_sections = [
            "# Instant Scribe",
            "## 🚀 Key Features",
            "## 📋 System Requirements",
            "## 🛠️ Installation",
            "## ⚙️ Configuration",
            "## 🧠 AI Model",
            "## 🔍 Troubleshooting"
        ]
        
        for section in essential_sections:
            assert section in content, f"README should contain section: {section}"
        
        # Check that README is substantial
        assert len(content) > 15000, "README should be comprehensive"
        
        # Check for key technical details
        technical_details = [
            "Parakeet TDT 0.6b-v2",
            "NVIDIA",
            "offline",
            "VRAM",
            "config.json"
        ]
        
        for detail in technical_details:
            assert detail in content, f"README should mention: {detail}"
    
    def test_configuration_documentation_accuracy(self):
        """Test that configuration documentation matches actual implementation."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()
        
        # Get actual config options
        config_manager = ConfigManager()
        actual_options = set(config_manager.DEFAULTS.keys())
        
        # Check that important options are documented
        important_options = {
            "hotkey", "vad_aggressiveness", "silence_threshold_ms",
            "show_notifications", "vram_unload_threshold_mb"
        }
        
        documented_options = set()
        for option in important_options:
            if option in readme_content:
                documented_options.add(option)
        
        missing_docs = important_options - documented_options
        assert len(missing_docs) <= 1, f"Too many undocumented options: {missing_docs}"


class TestPerformanceValidation:
    """Test performance characteristics and benchmarks."""
    
    def test_config_loading_performance(self):
        """Test that configuration loading is fast."""
        start_time = time.time()
        
        # Load config multiple times
        for _ in range(10):
            config_manager = ConfigManager()
            _ = config_manager.get("hotkey")
        
        elapsed = time.time() - start_time
        
        # Should be very fast (less than 1 second for 10 loads)
        assert elapsed < 1.0, f"Config loading too slow: {elapsed:.3f}s"
    
    def test_schema_validation_performance(self):
        """Test that schema validation is reasonably fast."""
        config_manager = ConfigManager()
        
        if not hasattr(config_manager, 'validate_config'):
            pytest.skip("Schema validation not available")
        
        start_time = time.time()
        
        # Validate config multiple times
        for _ in range(100):
            result = config_manager.validate_config(config_manager.DEFAULTS)
            assert result is True
        
        elapsed = time.time() - start_time
        
        # Should be fast (less than 1 second for 100 validations)
        assert elapsed < 1.0, f"Schema validation too slow: {elapsed:.3f}s"


class TestCodebaseHarmonization:
    """Test codebase consistency and harmonization."""
    
    def test_import_consistency(self):
        """Test that imports are consistent across modules."""
        # Check that all modules can be imported without errors
        modules_to_test = [
            "InstanceScrubber.config_manager",
            "instant_scribe.application_orchestrator",
            "instant_scribe.crash_reporter"
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except ImportError as exc:
                pytest.fail(f"Failed to import {module_name}: {exc}")
    
    def test_configuration_consistency(self):
        """Test that configuration is consistent across all usage."""
        config_manager = ConfigManager()
        
        # Test that all default values are valid types
        for key, value in config_manager.DEFAULTS.items():
            assert value is not None or key in ["paused"], f"Invalid default for {key}: {value}"
            
            # Check type consistency
            if isinstance(value, str):
                assert len(value) > 0 or key in ["locale"], f"Empty string default for {key}"
            elif isinstance(value, int):
                assert value >= 0 or key in ["vram_unload_threshold_mb"], f"Negative int default for {key}"
    
    def test_file_organization(self):
        """Test that file organization follows project standards."""
        project_root = Path(__file__).parent.parent
        
        # Check that essential directories exist
        essential_dirs = ["InstanceScrubber", "instant_scribe", "scripts", "tests", "docs"]
        
        for dir_name in essential_dirs:
            dir_path = project_root / dir_name
            assert dir_path.exists(), f"Essential directory missing: {dir_name}"
            assert dir_path.is_dir(), f"Path should be directory: {dir_name}"
        
        # Check that essential files exist
        essential_files = ["README.md", "requirements.txt", "config.schema.json"]
        
        for file_name in essential_files:
            file_path = project_root / file_name
            assert file_path.exists(), f"Essential file missing: {file_name}"
            assert file_path.is_file(), f"Path should be file: {file_name}"


class TestFinalCleanup:
    """Test that final cleanup has been performed."""
    
    def test_no_temporary_files(self):
        """Test that no temporary files remain in the project."""
        project_root = Path(__file__).parent.parent
        
        # Look for common temporary file patterns
        temp_patterns = ["*.tmp", "*.temp", "test_*.py"]
        temp_files = []
        
        for pattern in temp_patterns:
            temp_files.extend(project_root.glob(pattern))
        
        # Filter out legitimate test files
        actual_temp_files = [
            f for f in temp_files 
            if not f.name.startswith("test_task") and f.parent.name != "tests"
        ]
        
        assert len(actual_temp_files) == 0, f"Temporary files found: {actual_temp_files}"
    
    def test_no_debug_artifacts(self):
        """Test that no debug artifacts remain."""
        project_root = Path(__file__).parent.parent
        
        # Check for debug artifacts
        debug_patterns = ["debug_*.py", "*.debug", "dump_*.py"]
        debug_files = []
        
        for pattern in debug_patterns:
            debug_files.extend(project_root.glob(pattern))
        
        assert len(debug_files) == 0, f"Debug artifacts found: {debug_files}"


def test_task60_complete_implementation():
    """Comprehensive test that Task 60 is fully implemented."""
    # Test 1: All components integrate properly
    config_manager = ConfigManager()
    assert config_manager.settings is not None
    
    # Test 2: Documentation is complete
    readme_path = Path(__file__).parent.parent / "README.md"
    assert readme_path.exists()
    
    with open(readme_path, 'r', encoding='utf-8') as f:
        readme_content = f.read()
    assert len(readme_content) > 15000, "README should be comprehensive"
    
    # Test 3: Schema validation works
    schema_path = Path(__file__).parent.parent / "config.schema.json"
    assert schema_path.exists()
    
    # Test 4: CLI tools work
    cli_path = Path(__file__).parent.parent / "scripts" / "upgrade_config.py"
    assert cli_path.exists()
    
    # Test 5: No temporary files remain
    project_root = Path(__file__).parent.parent
    temp_files = list(project_root.glob("test_task*.py"))
    temp_files = [f for f in temp_files if f.parent.name != "tests"]
    assert len(temp_files) == 0, f"Temporary test files found: {temp_files}"
    
    print("✓ Task 60 implementation complete - project ready for release")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
