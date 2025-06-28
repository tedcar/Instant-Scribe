import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None  # type: ignore
    Draft202012Validator = None  # type: ignore
    _JSONSCHEMA_AVAILABLE = False

try:
    from InstanceScrubber.resource_manager import resource_path
    _RESOURCE_MANAGER_AVAILABLE = True
except ImportError:
    _RESOURCE_MANAGER_AVAILABLE = False


class ConfigManager:
    """Simple JSON-backed configuration loader / saver.

    The config file is stored in the user-specific application data directory.
    On Windows we honour the %APPDATA% convention. On *nix platforms we fall
    back to ~/.config.
    """

    _FILENAME = "config.json"

    #: Default configuration values shipped with Instant Scribe.
    DEFAULTS: Dict[str, Any] = {
        "hotkey": "ctrl+alt+f",
        "vad_aggressiveness": 2,
        "silence_threshold_ms": 120000,  # 2 minutes default threshold per PRD §3.2.5
        "batch_length_ms": 600000,       # 10-minute batches (Task 21 requirement)
        "batch_overlap_ms": 10000,       # 10-second overlap between batches (Task 21.3)
        "show_notifications": True,
        "copy_to_clipboard_on_click": True,
        "archive_root": r"C:\\Users\\%USERNAME%\\Documents\\[01] Documents\\[15] AI Recordings",
        "silence_prune_threshold_ms": 120000,  # Task 22 – long-silence pruning (> 2 min)
        # Task 24 – enhanced spooler chunk interval (seconds)
        "spooler_chunk_interval_sec": 60,
        # Task 33 – GPU resource management
        "vram_unload_threshold_mb": 1024,  # Auto-unload when free VRAM < 1 GB
        "gpu_monitor_interval_sec": 5,     # Polling interval in seconds
        # Task 37 – audio quality optimisations
        "enable_agc": False,
        "enable_noise_suppression": False,
        # Task 43 – telemetry & observability
        "telemetry_enabled": False,  # Opt-out by default
        # Task 44 – accessibility & UX enhancements
        "high_contrast_icons": False,  # Use high-contrast icon variants
        # Task 45 – high-DPI & multi-monitor support
        "dpi_check_interval_sec": 5,  # How often to check for DPI changes
        # Task 50 – internationalization & localization
        "locale": "en_US",  # Default locale
    }

    def __init__(self, app_name: str = "Instant Scribe") -> None:
        self.app_name = app_name
        self._config_path: Path = self._resolve_config_path()
        self.settings: Dict[str, Any] = {}
        self._schema: Optional[Dict[str, Any]] = None
        self._validator: Optional[Any] = None
        self._load_schema()
        self._load()

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Return the configuration value for *key*, or *default* if missing."""
        # If no explicit default provided, use DEFAULTS
        if default is None and key in self.DEFAULTS:
            default = self.DEFAULTS[key]
        return self.settings.get(key, default)

    def set(self, key: str, value: Any, *, auto_save: bool = True) -> None:
        """Set *key* to *value*. Optionally persist immediately."""
        self.settings[key] = value
        if auto_save:
            self._save()

    def reload(self) -> None:
        """Force reload configuration from disk, discarding local changes."""
        self._load()

    def validate_config(self, config_data: Dict[str, Any]) -> bool:
        """Validate configuration data against the JSON schema.

        Args:
            config_data: Configuration dictionary to validate

        Returns:
            True if validation passes, False otherwise
        """
        if not _JSONSCHEMA_AVAILABLE or not self._validator:
            logging.warning("JSON schema validation unavailable - skipping validation")
            return True

        try:
            self._validator.validate(config_data)
            return True
        except jsonschema.ValidationError as exc:
            logging.error("Configuration validation failed: %s", exc.message)
            logging.debug("Validation error details: %s", exc)
            return False
        except Exception as exc:
            logging.error("Unexpected error during config validation: %s", exc)
            return False

    def set_archive_directory(self, new_path: str | Path) -> bool:
        """Set a new archive directory path and validate it.

        Args:
            new_path: The new archive directory path. Can contain environment variables.

        Returns:
            True if the path was successfully set and validated, False otherwise.

        Raises:
            ValueError: If the path is invalid or cannot be created.
        """
        import os
        from pathlib import Path

        # Expand environment variables and resolve path
        expanded_path = os.path.expandvars(str(new_path))
        resolved_path = Path(expanded_path).expanduser().resolve()

        # Validate that we can create the directory
        try:
            resolved_path.mkdir(parents=True, exist_ok=True)
            if not resolved_path.is_dir():
                raise ValueError(f"Path exists but is not a directory: {resolved_path}")
        except (OSError, PermissionError) as exc:
            raise ValueError(f"Cannot create or access directory: {resolved_path}") from exc

        # Test write permissions
        test_file = resolved_path / ".instant_scribe_test"
        try:
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
        except (OSError, PermissionError) as exc:
            raise ValueError(f"No write permission for directory: {resolved_path}") from exc

        # Store the original path (with env vars) for portability
        self.set("archive_root", str(new_path))
        return True

    def set_locale(self, locale: str) -> bool:
        """Set the application locale and update i18n system.

        Args:
            locale: Locale code (e.g., 'en_US', 'es_ES')

        Returns:
            True if locale was successfully set, False otherwise.
        """
        try:
            # Import here to avoid circular imports
            from .i18n_manager import set_locale

            # Validate locale by attempting to set it
            if set_locale(locale):
                self.set("locale", locale)
                return True
            return False
        except ImportError:
            # i18n system not available, just store the setting
            self.set("locale", locale)
            return True

    # ------------------------------------------------------------------
    # Implementation details
    # ------------------------------------------------------------------
    def _load_schema(self) -> None:
        """Load and initialize the JSON schema for configuration validation."""
        if not _JSONSCHEMA_AVAILABLE:
            logging.debug("jsonschema library not available - schema validation disabled")
            return

        try:
            # Try to load schema from bundled resource first
            schema_path = None
            if _RESOURCE_MANAGER_AVAILABLE:
                try:
                    schema_path = resource_path("config.schema.json")
                except Exception:
                    pass

            # Fallback to local file
            if not schema_path or not Path(schema_path).exists():
                schema_path = Path(__file__).parent.parent / "config.schema.json"

            if Path(schema_path).exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    self._schema = json.load(f)
                self._validator = Draft202012Validator(self._schema)
                logging.debug("Configuration schema loaded successfully")
            else:
                logging.warning("Configuration schema file not found at %s", schema_path)
        except Exception as exc:
            logging.warning("Failed to load configuration schema: %s", exc)
            self._schema = None
            self._validator = None

    def _resolve_config_path(self) -> Path:
        """Compute platform-appropriate path for the JSON config."""
        # Prefer the *APPDATA* environment variable when set to provide
        # predictable behaviour in test environments that monkey-patch the
        # variable regardless of the host OS.  This keeps the logic simple
        # and aligns with the expectations asserted in *tests/test_config_manager.py*.
        if "APPDATA" in os.environ and os.environ["APPDATA"]:
            base_dir = Path(os.environ["APPDATA"])
        elif os.name == "nt":
            # Windows hosts fall back to the real %APPDATA% location if the
            # variable is missing (unlikely) to avoid writing to the user's
            # home directory.
            base_dir = Path(Path.home())
        else:
            # Cross-platform default: honour XDG if available, otherwise use
            # ~/.config to avoid cluttering the home directory root.
            base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

        path = base_dir / self.app_name.replace(" ", "_") / self._FILENAME
        return path

    def _load(self) -> None:
        """Load settings from disk, creating the file with defaults if absent."""
        try:
            if self._config_path.exists():
                with self._config_path.open("r", encoding="utf-8") as fh:
                    loaded_settings = json.load(fh)

                # Validate loaded configuration
                if self.validate_config(loaded_settings):
                    self.settings = loaded_settings
                    logging.debug("Configuration loaded and validated successfully")
                else:
                    logging.warning("Configuration validation failed - using defaults")
                    self.settings = self.DEFAULTS.copy()
                    # Write corrected defaults back to disk
                    try:
                        self._write_to_disk(self.settings)
                    except Exception as write_exc:
                        logging.error("Unable to write corrected config: %s", write_exc)
            else:
                self.settings = self.DEFAULTS.copy()
                self._write_to_disk(self.settings)
        except (json.JSONDecodeError, OSError) as exc:
            logging.warning("Failed to load config – using defaults: %s", exc)
            self.settings = self.DEFAULTS.copy()
            # Attempt to overwrite the corrupted file with defaults.
            try:
                self._write_to_disk(self.settings)
            except Exception as write_exc:
                logging.error("Unable to write default config: %s", write_exc)

    def _save(self) -> None:
        """Persist current *settings* to disk."""
        # Validate before saving
        if not self.validate_config(self.settings):
            logging.error("Configuration validation failed - not saving invalid config")
            return
        self._write_to_disk(self.settings)

    def _write_to_disk(self, data: Dict[str, Any]) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4)

    # ------------------------------------------------------------------
    # Convenience dunder methods
    # ------------------------------------------------------------------
    def __getitem__(self, item: str) -> Any:  # dict-style access
        return self.settings[item]

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, item: str) -> bool:
        return item in self.settings

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ConfigManager path={self._config_path!s} keys={list(self.settings.keys())}>" 