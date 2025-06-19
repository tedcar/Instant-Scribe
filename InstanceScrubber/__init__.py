"""Instant Scribe core package.

Exposes commonly used helpers at the package root for convenience.
"""

from .config_manager import ConfigManager  # noqa: F401
from .logging_config import setup_logging  # noqa: F401
from .resource_manager import resource_path  # noqa: F401 