"""Portable mode detection and path resolution utilities.

This module provides utilities to detect when Instant Scribe is running in portable mode
and handles path resolution accordingly. Portable mode is detected by the presence of a
'portable.txt' file in the same directory as the executable.

In portable mode:
- Configuration and data files are stored relative to the executable directory
- No registry writes are performed
- All paths are resolved relative to the application directory
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def is_portable_mode() -> bool:
    """Check if the application is running in portable mode.
    
    Portable mode is detected by the presence of a 'portable.txt' file
    in the same directory as the executable.
    
    Returns:
        True if running in portable mode, False otherwise.
    """
    executable_dir = get_executable_directory()
    portable_marker = executable_dir / "portable.txt"
    return portable_marker.exists()


def get_executable_directory() -> Path:
    """Get the directory containing the executable.
    
    This works for both frozen (PyInstaller) and development environments.
    
    Returns:
        Path to the directory containing the executable.
    """
    if getattr(sys, "frozen", False):
        # Running as PyInstaller executable
        return Path(sys.executable).parent
    else:
        # Running in development mode - use the project root
        return Path(__file__).resolve().parent.parent


def get_portable_data_directory() -> Path:
    """Get the data directory for portable mode.
    
    In portable mode, data is stored in a 'data' subdirectory
    relative to the executable.
    
    Returns:
        Path to the portable data directory.
    """
    return get_executable_directory() / "data"


def get_config_path(app_name: str = "Instant Scribe") -> Path:
    """Get the configuration file path, considering portable mode.
    
    Args:
        app_name: Name of the application.
        
    Returns:
        Path to the configuration file.
    """
    if is_portable_mode():
        data_dir = get_portable_data_directory()
        return data_dir / "config.json"
    else:
        # Use standard system paths
        if os.name == "nt":
            base_dir = Path(os.environ.get("APPDATA", Path.home()))
        else:
            base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        
        return base_dir / app_name.replace(" ", "_") / "config.json"


def get_data_path(relative_path: str) -> Path:
    """Get a data file path, considering portable mode.
    
    Args:
        relative_path: Relative path to the data file.
        
    Returns:
        Absolute path to the data file.
    """
    if is_portable_mode():
        return get_portable_data_directory() / relative_path
    else:
        # Use standard system paths
        if os.name == "nt":
            base_dir = Path(os.environ.get("APPDATA", Path.home()))
        else:
            base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        
        return base_dir / "Instant_Scribe" / relative_path


def get_temp_directory() -> Path:
    """Get the temporary directory for spooling, considering portable mode.
    
    Returns:
        Path to the temporary directory.
    """
    if is_portable_mode():
        return get_portable_data_directory() / "temp"
    else:
        # Use standard system paths
        appdata = os.getenv("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            import tempfile
            base = Path(tempfile.gettempdir())
        return base / "Instant Scribe" / "temp"


def get_archive_directory() -> Optional[Path]:
    """Get the archive directory, considering portable mode.
    
    Returns:
        Path to the archive directory, or None if not configured.
    """
    if is_portable_mode():
        return get_portable_data_directory() / "archives"
    else:
        # Return None to use the configured archive_root from config
        return None


def ensure_portable_directories() -> None:
    """Ensure all necessary directories exist in portable mode."""
    if not is_portable_mode():
        return
    
    data_dir = get_portable_data_directory()
    directories = [
        data_dir,
        data_dir / "temp",
        data_dir / "archives",
        data_dir / "logs",
        data_dir / "reports",
        data_dir / "metrics",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def create_portable_marker() -> None:
    """Create the portable mode marker file."""
    executable_dir = get_executable_directory()
    portable_marker = executable_dir / "portable.txt"
    
    with open(portable_marker, "w", encoding="utf-8") as f:
        f.write("This file indicates that Instant Scribe is running in portable mode.\n")
        f.write("All configuration and data files will be stored relative to this directory.\n")
        f.write("Delete this file to switch back to standard installation mode.\n")
