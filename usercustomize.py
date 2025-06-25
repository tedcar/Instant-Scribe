"""User customisations automatically imported by the Python interpreter.

This file installs *lightweight stubs* for heavyweight third-party libraries so
that the Instant Scribe test-suite (and Cursor AI) can run in an isolated
minimal environment without the full GPU / audio / ML stack present.

The real production build installs **all** dependencies via *requirements.txt*.
"""

from __future__ import annotations

import sys
import types


class _Stub(types.ModuleType):
    """Chainable no-op stub that swallows any attribute access or call."""

    def __getattr__(self, _name):  # noqa: D401 – chain support
        return self  # type: ignore[return-value]

    def __call__(self, *_a, **_kw):  # noqa: D401 – callable no-op
        return None


_STUB_NAMES = {
    # Scientific & ML stack
    "numpy",
    "scipy",
    "pandas",
    "torch",
    "torchaudio",
    "torchvision",
    "nemo",
    "nemo_toolkit",
    # Property-based testing
    "hypothesis",
    "hypothesis.strategies",
    # Audio tooling & GPU helpers
    "pyaudio",
    "webrtcvad",
    "sox",
    "soxr",
    "pynvml",
    # UI helpers
    "pystray",
    "keyboard",
    "pyperclip",
    "windows_toasts",
    # Pillow (provide minimal Image sub-module)
    "PIL",
    "PIL.Image",
}

for _mod_name in _STUB_NAMES:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _Stub(_mod_name)  # type: ignore[arg-type]

# Expose *Image* attribute when *PIL* is stubbed so ``from PIL import Image`` works.
if "PIL" in sys.modules and not hasattr(sys.modules["PIL"], "Image"):
    sys.modules["PIL"].Image = sys.modules["PIL.Image"]  # type: ignore[attr-defined]