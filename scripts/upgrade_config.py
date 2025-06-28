#!/usr/bin/env python3
"""Configuration Migration and Validation Tool - Task 58.2

This CLI tool provides functionality to:
1. Migrate older configuration files to the current schema
2. Validate existing configuration files against the JSON schema
3. Fix common configuration issues automatically
4. Generate a new configuration file with current defaults

Usage:
    python scripts/upgrade_config.py --validate
    python scripts/upgrade_config.py --migrate
    python scripts/upgrade_config.py --fix
    python scripts/upgrade_config.py --generate-defaults
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None  # type: ignore
    Draft202012Validator = None  # type: ignore
    _JSONSCHEMA_AVAILABLE = False

try:
    from InstanceScrubber.config_manager import ConfigManager
    _CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    _CONFIG_MANAGER_AVAILABLE = False


def load_schema() -> Optional[Dict[str, Any]]:
    """Load the configuration schema from file."""
    schema_path = Path(__file__).parent.parent / "config.schema.json"
    if not schema_path.exists():
        print(f"ERROR: Schema file not found at {schema_path}")
        return None
    
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as exc:
        print(f"ERROR: Failed to load schema: {exc}")
        return None


def validate_config_file(config_path: Path, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a configuration file against the schema.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    if not _JSONSCHEMA_AVAILABLE:
        return False, ["jsonschema library not available"]
    
    if not config_path.exists():
        return False, [f"Configuration file not found: {config_path}"]
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except Exception as exc:
        return False, [f"Failed to load config file: {exc}"]
    
    validator = Draft202012Validator(schema)
    errors = []
    
    for error in validator.iter_errors(config_data):
        error_path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{error_path}: {error.message}")
    
    return len(errors) == 0, errors


def migrate_config(config_path: Path, schema: Dict[str, Any]) -> bool:
    """Migrate an older configuration file to the current schema.
    
    Returns:
        True if migration was successful, False otherwise
    """
    if not config_path.exists():
        print(f"Configuration file not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            old_config = json.load(f)
    except Exception as exc:
        print(f"Failed to load existing config: {exc}")
        return False
    
    # Get default values from schema
    defaults = {}
    if "properties" in schema:
        for key, prop in schema["properties"].items():
            if "default" in prop:
                defaults[key] = prop["default"]
    
    # Create migrated config by merging old config with defaults
    migrated_config = defaults.copy()
    migrated_config.update(old_config)
    
    # Remove any keys not in the schema
    if "properties" in schema:
        valid_keys = set(schema["properties"].keys())
        migrated_config = {k: v for k, v in migrated_config.items() if k in valid_keys}
    
    # Validate the migrated config
    if _JSONSCHEMA_AVAILABLE:
        validator = Draft202012Validator(schema)
        try:
            validator.validate(migrated_config)
        except jsonschema.ValidationError as exc:
            print(f"Migration failed - validation error: {exc.message}")
            return False
    
    # Create backup of original
    backup_path = config_path.with_suffix('.json.backup')
    try:
        config_path.rename(backup_path)
        print(f"Original config backed up to: {backup_path}")
    except Exception as exc:
        print(f"Warning: Failed to create backup: {exc}")
    
    # Write migrated config
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(migrated_config, f, indent=4)
        print(f"Configuration migrated successfully: {config_path}")
        return True
    except Exception as exc:
        print(f"Failed to write migrated config: {exc}")
        # Try to restore backup
        if backup_path.exists():
            try:
                backup_path.rename(config_path)
                print("Original config restored from backup")
            except Exception:
                pass
        return False


def fix_config(config_path: Path, schema: Dict[str, Any]) -> bool:
    """Fix common configuration issues automatically.
    
    Returns:
        True if fixes were applied successfully, False otherwise
    """
    if not config_path.exists():
        print(f"Configuration file not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except Exception as exc:
        print(f"Failed to load config file: {exc}")
        return False
    
    fixes_applied = []
    
    # Fix 1: Remove invalid keys
    if "properties" in schema:
        valid_keys = set(schema["properties"].keys())
        invalid_keys = set(config_data.keys()) - valid_keys
        for key in invalid_keys:
            del config_data[key]
            fixes_applied.append(f"Removed invalid key: {key}")
    
    # Fix 2: Add missing required keys with defaults
    if "properties" in schema:
        for key, prop in schema["properties"].items():
            if key not in config_data and "default" in prop:
                config_data[key] = prop["default"]
                fixes_applied.append(f"Added missing key with default: {key}")
    
    # Fix 3: Correct invalid types
    if "properties" in schema and _JSONSCHEMA_AVAILABLE:
        for key, prop in schema["properties"].items():
            if key in config_data:
                expected_type = prop.get("type")
                current_value = config_data[key]
                
                if expected_type == "integer" and isinstance(current_value, str):
                    try:
                        config_data[key] = int(current_value)
                        fixes_applied.append(f"Converted {key} from string to integer")
                    except ValueError:
                        if "default" in prop:
                            config_data[key] = prop["default"]
                            fixes_applied.append(f"Reset {key} to default due to invalid value")
                
                elif expected_type == "boolean" and isinstance(current_value, str):
                    if current_value.lower() in ("true", "1", "yes"):
                        config_data[key] = True
                        fixes_applied.append(f"Converted {key} from string to boolean (true)")
                    elif current_value.lower() in ("false", "0", "no"):
                        config_data[key] = False
                        fixes_applied.append(f"Converted {key} from string to boolean (false)")
                    elif "default" in prop:
                        config_data[key] = prop["default"]
                        fixes_applied.append(f"Reset {key} to default due to invalid value")
    
    if not fixes_applied:
        print("No fixes needed - configuration is already valid")
        return True
    
    # Write fixed config
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        
        print(f"Applied {len(fixes_applied)} fixes:")
        for fix in fixes_applied:
            print(f"  - {fix}")
        print(f"Fixed configuration saved to: {config_path}")
        return True
    except Exception as exc:
        print(f"Failed to write fixed config: {exc}")
        return False


def generate_defaults(output_path: Path, schema: Dict[str, Any]) -> bool:
    """Generate a new configuration file with all default values.
    
    Returns:
        True if generation was successful, False otherwise
    """
    defaults = {}
    
    if "properties" in schema:
        for key, prop in schema["properties"].items():
            if "default" in prop:
                defaults[key] = prop["default"]
    
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(defaults, f, indent=4)
        print(f"Default configuration generated: {output_path}")
        return True
    except Exception as exc:
        print(f"Failed to generate default config: {exc}")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Instant Scribe Configuration Migration and Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --validate                    # Validate current config
  %(prog)s --validate --config custom.json  # Validate specific file
  %(prog)s --migrate                     # Migrate current config
  %(prog)s --fix                         # Fix common issues
  %(prog)s --generate-defaults           # Generate new config with defaults
        """
    )
    
    parser.add_argument(
        "--validate", 
        action="store_true",
        help="Validate configuration file against schema"
    )
    parser.add_argument(
        "--migrate",
        action="store_true", 
        help="Migrate older configuration to current schema"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix common configuration issues automatically"
    )
    parser.add_argument(
        "--generate-defaults",
        action="store_true",
        help="Generate new configuration file with default values"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file (default: auto-detect)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for generated config (default: config.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    
    # Check dependencies
    if not _JSONSCHEMA_AVAILABLE:
        print("ERROR: jsonschema library not available. Install with: pip install jsonschema")
        return 1
    
    # Load schema
    schema = load_schema()
    if not schema:
        return 1
    
    # Determine config file path
    if args.config:
        config_path = args.config
    elif _CONFIG_MANAGER_AVAILABLE:
        try:
            config_manager = ConfigManager()
            config_path = config_manager._config_path
        except Exception:
            config_path = Path("data/config.json")
    else:
        config_path = Path("data/config.json")
    
    # Execute requested action
    if args.validate:
        is_valid, errors = validate_config_file(config_path, schema)
        if is_valid:
            print(f"OK Configuration is valid: {config_path}")
            return 0
        else:
            print(f"ERROR Configuration validation failed: {config_path}")
            for error in errors:
                print(f"  - {error}")
            return 1
    
    elif args.migrate:
        success = migrate_config(config_path, schema)
        return 0 if success else 1
    
    elif args.fix:
        success = fix_config(config_path, schema)
        return 0 if success else 1
    
    elif args.generate_defaults:
        output_path = args.output or Path("config.json")
        success = generate_defaults(output_path, schema)
        return 0 if success else 1
    
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
