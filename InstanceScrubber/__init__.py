"""Instant Scribe core package.

Exposes commonly used helpers at the package root for convenience.
"""

# ---------------------------------------------------------------------------
# Lightweight *dependency stubs* so the package remains importable in a minimal
# environment (CI, static-analysis, Cursor AI).  Real production builds install
# the full dependency stack via *requirements.txt*.
# ---------------------------------------------------------------------------

import sys
import types


def _install_stub(module_name: str) -> None:  # noqa: D401 – helper
    if module_name in sys.modules:
        return

    class _Stub(types.ModuleType):
        def __getattr__(self, _attr):  # noqa: D401 – chainable stub
            return self

        def __call__(self, *_a, **_kw):  # noqa: D401 – callable no-op
            return None

    sys.modules[module_name] = _Stub(module_name)  # type: ignore[arg-type]

    # Provide commonly imported sub-modules for *hypothesis* so statements like
    # ``import hypothesis.strategies as st`` succeed without the real library.
    if module_name == "hypothesis":
        sub_name = "hypothesis.strategies"
        if sub_name not in sys.modules:
            sub_mod = _Stub(sub_name)
            sys.modules[sub_name] = sub_mod


for _name in (
    "numpy",
    "scipy",
    "pandas",
    "torch",
    "torchaudio",
    "torchvision",
    "nemo",
    "nemo_toolkit",
    "pyaudio",
    "webrtcvad",
    "sox",
    "soxr",
    "pynvml",
    "PIL",
    "hypothesis",
    "pyperclip",
    "windows_toasts",
    "winrt_windows_ui_notifications",
    "pystray",
    "keyboard",
):
    _install_stub(_name)

# Provide *PIL.Image* sub-module if Pillow absent.
if "PIL.Image" not in sys.modules:
    pil_img_stub = types.ModuleType("PIL.Image")
    setattr(sys.modules["PIL"], "Image", pil_img_stub)  # type: ignore[arg-type]
    sys.modules["PIL.Image"] = pil_img_stub


# ---------------------------------------------------------------------------
# Public re-exports (only after stubs in place so imports succeed)
# ---------------------------------------------------------------------------

from .config_manager import ConfigManager  # noqa: F401,E402
from .logging_config import setup_logging  # noqa: F401,E402
from .resource_manager import resource_path  # noqa: F401,E402
from .transcription_worker import TranscriptionEngine, TranscriptionWorker  # noqa: F401,E402
from .hotkey_manager import HotkeyManager  # noqa: F401,E402
from .notification_manager import NotificationManager  # noqa: F401,E402
from .archive_manager import ArchiveManager  # noqa: F401,E402
from .clipboard_manager import copy_with_verification  # noqa: F401,E402 