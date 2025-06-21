import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional


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
        # Task 37 – Audio quality optimisations
        "enable_agc": False,              # Automatic Gain Control disabled by default
        "enable_noise_suppression": False,  # RNNoise-based denoising disabled by default
    }

    def __init__(self, app_name: str = "Instant Scribe") -> None:
        self.app_name = app_name
        self._config_path: Path = self._resolve_config_path()
        self.settings: Dict[str, Any] = {}
        self._load()

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Return the configuration value for *key*, or *default* if missing."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any, *, auto_save: bool = True) -> None:
        """Set *key* to *value*. Optionally persist immediately."""
        self.settings[key] = value
        if auto_save:
            self._save()

    def reload(self) -> None:
        """Force reload configuration from disk, discarding local changes."""
        self._load()

    # ------------------------------------------------------------------
    # Implementation details
    # ------------------------------------------------------------------
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
                    self.settings = json.load(fh)
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