"""Instant Scribe core package.

Exposes commonly used helpers at the package root for convenience.
"""

from .config_manager import ConfigManager  # noqa: F401
from .logging_config import setup_logging  # noqa: F401
from .resource_manager import resource_path  # noqa: F401
from .transcription_worker import TranscriptionEngine, TranscriptionWorker  # noqa: F401
from .hotkey_manager import HotkeyManager  # noqa: F401
from .notification_manager import NotificationManager  # noqa: F401
from .archive_manager import ArchiveManager  # noqa: F401
from .clipboard_manager import copy_with_verification  # noqa: F401 