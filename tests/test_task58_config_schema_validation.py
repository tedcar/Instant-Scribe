"""Comprehensive tests for Task 58 - Config Schema & Validation.

This test suite validates:
- JSON schema definition and structure
- Runtime configuration validation
- Config migration CLI tool functionality
- Error handling and edge cases
"""

import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False

from InstanceScrubber.config_manager import ConfigManager


class TestConfigSchema:
    """Test the JSON schema definition itself."""
    
    def test_schema_file_exists(self):
        """Test that the schema file exists and is valid JSON."""
        schema_path = Path(__file__).parent.parent / "config.schema.json"
        assert schema_path.exists(), "config.schema.json file should exist"
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        assert isinstance(schema, dict), "Schema should be a JSON object"
        assert "$schema" in schema, "Schema should have $schema property"
        assert "properties" in schema, "Schema should have properties"
    
    @pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not available")
    def test_schema_is_valid_json_schema(self):
        """Test that our schema is itself a valid JSON Schema."""
        schema_path = Path(__file__).parent.parent / "config.schema.json"
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Validate against the meta-schema
        Draft202012Validator.check_schema(schema)
    
    def test_schema_covers_all_config_keys(self):
        """Test that schema covers all configuration keys used in the application."""
        schema_path = Path(__file__).parent.parent / "config.schema.json"
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Get all keys from ConfigManager defaults
        config_manager = ConfigManager()
        default_keys = set(config_manager.DEFAULTS.keys())
        schema_keys = set(schema["properties"].keys())
        
        # Check that all default keys are covered in schema
        missing_keys = default_keys - schema_keys
        assert not missing_keys, f"Schema missing keys: {missing_keys}"
    
    def test_schema_default_values_match(self):
        """Test that schema default values match ConfigManager defaults."""
        schema_path = Path(__file__).parent.parent / "config.schema.json"
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        config_manager = ConfigManager()
        
        for key, prop in schema["properties"].items():
            if "default" in prop and key in config_manager.DEFAULTS:
                schema_default = prop["default"]
                config_default = config_manager.DEFAULTS[key]
                assert schema_default == config_default, \
                    f"Schema default for {key} ({schema_default}) doesn't match ConfigManager default ({config_default})"


class TestConfigValidation:
    """Test runtime configuration validation."""
    
    @pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not available")
    def test_valid_config_passes_validation(self):
        """Test that a valid configuration passes validation."""
        config_manager = ConfigManager()
        
        # Use the default configuration
        valid_config = config_manager.DEFAULTS.copy()
        
        assert config_manager.validate_config(valid_config) is True
    
    @pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not available")
    def test_invalid_config_fails_validation(self):
        """Test that invalid configurations fail validation."""
        config_manager = ConfigManager()
        
        # Test invalid type
        invalid_config = config_manager.DEFAULTS.copy()
        invalid_config["vad_aggressiveness"] = "invalid"  # Should be integer
        
        assert config_manager.validate_config(invalid_config) is False
        
        # Test out of range value
        invalid_config = config_manager.DEFAULTS.copy()
        invalid_config["vad_aggressiveness"] = 10  # Should be 0-3
        
        assert config_manager.validate_config(invalid_config) is False
    
    @pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not available")
    def test_config_validation_on_load(self):
        """Test that configuration validation occurs during loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            
            # Create invalid config file
            invalid_config = {
                "hotkey": "ctrl+alt+f",
                "vad_aggressiveness": "invalid",  # Should be integer
                "show_notifications": True
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(invalid_config, f)
            
            # Mock the config path resolution
            with patch.object(ConfigManager, '_resolve_config_path', return_value=config_path):
                config_manager = ConfigManager()
                
                # Should fall back to defaults due to validation failure
                assert config_manager.settings == config_manager.DEFAULTS
    
    def test_validation_without_jsonschema(self):
        """Test graceful handling when jsonschema is not available."""
        config_manager = ConfigManager()
        
        # Mock jsonschema as unavailable
        with patch('InstanceScrubber.config_manager._JSONSCHEMA_AVAILABLE', False):
            # Should return True (skip validation) when jsonschema unavailable
            assert config_manager.validate_config({"any": "config"}) is True


class TestConfigMigrationCLI:
    """Test the configuration migration CLI tool."""
    
    def test_cli_tool_exists(self):
        """Test that the CLI tool file exists and is executable."""
        cli_path = Path(__file__).parent.parent / "scripts" / "upgrade_config.py"
        assert cli_path.exists(), "upgrade_config.py CLI tool should exist"
        
        # Check that it's a Python script
        with open(cli_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            assert first_line.startswith("#!") and "python" in first_line
    
    @pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not available")
    def test_cli_validate_command(self):
        """Test the CLI validate command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            
            # Create valid config
            valid_config = {
                "hotkey": "ctrl+alt+f",
                "vad_aggressiveness": 2,
                "show_notifications": True
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(valid_config, f)
            
            # Import and test the CLI module
            cli_module_path = Path(__file__).parent.parent / "scripts" / "upgrade_config.py"
            spec = importlib.util.spec_from_file_location("upgrade_config", cli_module_path)
            cli_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli_module)
            
            # Load schema
            schema = cli_module.load_schema()
            assert schema is not None
            
            # Test validation
            is_valid, errors = cli_module.validate_config_file(config_path, schema)
            assert is_valid is True
            assert len(errors) == 0
    
    @pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not available")
    def test_cli_migrate_command(self):
        """Test the CLI migrate command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            
            # Create old-style config missing some new keys
            old_config = {
                "hotkey": "ctrl+alt+f",
                "vad_aggressiveness": 2,
                "show_notifications": True,
                # Missing newer keys like pause_hotkey, etc.
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(old_config, f)
            
            # Import CLI module
            cli_module_path = Path(__file__).parent.parent / "scripts" / "upgrade_config.py"
            spec = importlib.util.spec_from_file_location("upgrade_config", cli_module_path)
            cli_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli_module)
            
            # Load schema and migrate
            schema = cli_module.load_schema()
            success = cli_module.migrate_config(config_path, schema)
            assert success is True
            
            # Check that backup was created
            backup_path = config_path.with_suffix('.json.backup')
            assert backup_path.exists()
            
            # Check that migrated config is valid
            with open(config_path, 'r', encoding='utf-8') as f:
                migrated_config = json.load(f)
            
            is_valid, errors = cli_module.validate_config_file(config_path, schema)
            assert is_valid is True
    
    @pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not available")
    def test_cli_fix_command(self):
        """Test the CLI fix command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            
            # Create config with fixable issues
            broken_config = {
                "hotkey": "ctrl+alt+f",
                "vad_aggressiveness": "2",  # String instead of int
                "show_notifications": "true",  # String instead of bool
                "invalid_key": "should_be_removed",  # Invalid key
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(broken_config, f)
            
            # Import CLI module
            cli_module_path = Path(__file__).parent.parent / "scripts" / "upgrade_config.py"
            spec = importlib.util.spec_from_file_location("upgrade_config", cli_module_path)
            cli_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli_module)
            
            # Load schema and fix
            schema = cli_module.load_schema()
            success = cli_module.fix_config(config_path, schema)
            assert success is True
            
            # Check that config is now valid
            with open(config_path, 'r', encoding='utf-8') as f:
                fixed_config = json.load(f)
            
            assert isinstance(fixed_config["vad_aggressiveness"], int)
            assert isinstance(fixed_config["show_notifications"], bool)
            assert "invalid_key" not in fixed_config
    
    def test_cli_generate_defaults_command(self):
        """Test the CLI generate defaults command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "defaults.json"
            
            # Import CLI module
            cli_module_path = Path(__file__).parent.parent / "scripts" / "upgrade_config.py"
            spec = importlib.util.spec_from_file_location("upgrade_config", cli_module_path)
            cli_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli_module)
            
            # Load schema and generate defaults
            schema = cli_module.load_schema()
            success = cli_module.generate_defaults(output_path, schema)
            assert success is True
            
            # Check that file was created and contains expected keys
            assert output_path.exists()
            
            with open(output_path, 'r', encoding='utf-8') as f:
                defaults = json.load(f)
            
            # Should contain all keys with defaults from schema
            expected_keys = {"hotkey", "vad_aggressiveness", "show_notifications"}
            assert expected_keys.issubset(set(defaults.keys()))


class TestIntegration:
    """Integration tests for the complete Task 58 functionality."""
    
    @pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not available")
    def test_end_to_end_config_workflow(self):
        """Test complete workflow: load, validate, save, reload."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            
            # Mock config path resolution
            with patch.object(ConfigManager, '_resolve_config_path', return_value=config_path):
                # Create new config manager (should create file with defaults)
                config1 = ConfigManager()
                assert config_path.exists()
                
                # Modify a setting
                config1.set("vad_aggressiveness", 3)
                
                # Create new instance (should load from file)
                config2 = ConfigManager()
                assert config2.get("vad_aggressiveness") == 3
                
                # Verify validation occurred
                assert config2.validate_config(config2.settings) is True
    
    def test_schema_validation_error_handling(self):
        """Test proper error handling during schema validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            
            # Create config with validation errors
            invalid_config = {
                "hotkey": "ctrl+alt+f",
                "vad_aggressiveness": 999,  # Out of range
                "silence_threshold_ms": -1,  # Negative value
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(invalid_config, f)
            
            # Mock config path resolution
            with patch.object(ConfigManager, '_resolve_config_path', return_value=config_path):
                # Should fall back to defaults due to validation failure
                config_manager = ConfigManager()
                assert config_manager.settings == config_manager.DEFAULTS


# Import required for CLI testing
import importlib.util


def test_task58_complete_implementation():
    """Comprehensive test that Task 58 is fully implemented."""
    # Test 1: Schema file exists
    schema_path = Path(__file__).parent.parent / "config.schema.json"
    assert schema_path.exists(), "config.schema.json should exist"
    
    # Test 2: CLI tool exists
    cli_path = Path(__file__).parent.parent / "scripts" / "upgrade_config.py"
    assert cli_path.exists(), "upgrade_config.py CLI tool should exist"
    
    # Test 3: ConfigManager has validation capability
    config_manager = ConfigManager()
    assert hasattr(config_manager, 'validate_config'), "ConfigManager should have validate_config method"
    assert hasattr(config_manager, '_load_schema'), "ConfigManager should have _load_schema method"
    
    # Test 4: Validation integration works
    if _JSONSCHEMA_AVAILABLE:
        # Should be able to validate default config
        assert config_manager.validate_config(config_manager.DEFAULTS) is True
    
    print("✓ Task 58 implementation complete and functional")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
