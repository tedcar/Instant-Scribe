"""Instant Scribe core package.

Exposes commonly used helpers at the package root for convenience.
"""

from .config_manager import ConfigManager  # noqa: F401
from .logging_config import setup_logging  # noqa: F401
from .resource_manager import resource_path  # noqa: F401

# Optional heavyweight components – wrapped in *try/except* so that unit tests
# which do not require the full GPU/ML stack (e.g. on minimal CI runners) can
# still import the *InstanceScrubber* package without raising `ImportError`.

try:
    from .transcription_worker import TranscriptionEngine, TranscriptionWorker  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover – optional dependency missing
    # Defer heavy dependencies (NumPy, PyTorch, etc.)
    pass

# Lightweight helpers are safe to import unconditionally
from .archive_manager import ArchiveManager  # noqa: F401
from .backup_manager import BackupManager  # noqa: F401

# Optional desktop-integration helpers – wrap to keep headless test env happy
try:
    from .notification_manager import NotificationManager  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    pass

try:
    from .hotkey_manager import HotkeyManager  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    pass

# Clipboard features rely on external packages; ignore if unavailable
try:
    from .clipboard_manager import copy_with_verification  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    pass 