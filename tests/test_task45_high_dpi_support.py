from __future__ import annotations

"""Task 45 – High-DPI & Multi-Monitor Support

This test module validates that:

1. The automatically generated *icon.ico* includes a **256×256** asset so it
   renders crisply on 4 K / 8 K displays.
2. The :pymeth:`InstanceScrubber.tray_app.TrayApp` reloads the tray icon when a
   system-DPI change is detected.  The behaviour is simulated by monkey-patching
   :pyfunc:`TrayApp._get_system_dpi` to return a different value on the second
   invocation and asserting that the underlying *pystray* stub receives an
   *update_icon* call.
"""

import inspect
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Ensure repository root is on *sys.path* so local imports resolve irrespective
# of where `pytest` is invoked from.
# ---------------------------------------------------------------------------
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# ---------------------------------------------------------------------------
# Re-usable *pystray* stubs (extended with *update_icon* flag for verification)
# ---------------------------------------------------------------------------
class _StubMenu(tuple):
    SEPARATOR = object()

    def __new__(cls, *items):  # noqa: D401 – mimic pystray.Menu signature
        return super().__new__(cls, items)


class _StubMenuItem:  # noqa: D401 – minimal placeholder
    def __init__(self, text, action=None, enabled=True):
        self._text = text
        self.action = action
        self.enabled = enabled

    @property
    def text(self):
        """Return the text for compatibility with real pystray."""
        return self._text(_) if callable(self._text) else self._text

    def __call__(self, _=None):
        return self._text(_) if callable(self._text) else self._text


class _StubIcon:
    def __init__(self, name, icon, title, menu):  # noqa: D401 – signature match
        self.name = name
        self.icon = icon
        self.title = title
        self.menu = menu
        self.menu_updated = False
        self.icon_updated = False

    # Methods referenced by *TrayApp*
    def run(self):  # noqa: D401 – stub (no GUI loop)
        pass

    def stop(self):  # noqa: D401 – stub
        pass

    def update_menu(self):  # noqa: D401 – tray_app fallback path
        self.menu_updated = True

    def update_icon(self):  # noqa: D401 – primary path on modern pystray
        self.icon_updated = True


@pytest.fixture(autouse=True)
def _patch_pystray(monkeypatch):
    """Inject *pystray* module stub for the duration of each test."""
    import importlib

    # Store original pystray module if it exists
    original_pystray = sys.modules.get("pystray")

    # Create and install stub
    stub = ModuleType("pystray")
    stub.Menu = _StubMenu  # type: ignore[attr-defined]
    stub.MenuItem = _StubMenuItem  # type: ignore[attr-defined]
    stub.Icon = _StubIcon  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pystray", stub)

    # Force reload of tray_app module to pick up the stub
    if "InstanceScrubber.tray_app" in sys.modules:
        importlib.reload(sys.modules["InstanceScrubber.tray_app"])

    yield

    # Restore original pystray module
    if original_pystray is not None:
        monkeypatch.setitem(sys.modules, "pystray", original_pystray)
    else:
        monkeypatch.delitem(sys.modules, "pystray", raising=False)

    # Reload tray_app again to restore original pystray
    if "InstanceScrubber.tray_app" in sys.modules:
        importlib.reload(sys.modules["InstanceScrubber.tray_app"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _DummyConfig:  # noqa: D401 – minimal ConfigManager replacement
    def get(self, *_):
        return None


def _cycle(values: list[int]) -> Iterator[int]:
    """Return iterator popping first item then repeating last one for ever."""
    while values:
        current = values.pop(0)
        yield current
    while True:
        yield current  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_placeholder_icon_contains_256(tmp_path, monkeypatch):
    """Generated placeholder *.ico* must include a 256×256 frame (Task 45.1)."""

    # Late import so the *pystray* stub is already in place.
    from InstanceScrubber import tray_app as tray_mod

    # Patch *resource_path* → tmp to avoid polluting repository.
    monkeypatch.setattr(tray_mod, "resource_path", lambda rel: tmp_path / rel)

    # Force icon generation by instantiating the TrayApp (no start required).
    app = tray_mod.TrayApp(_DummyConfig(), lambda: None, lambda: None)
    icon_path = (tmp_path / "assets" / "icon.ico")
    assert icon_path.exists() is False  # ensure clean slate

    # Trigger placeholder creation
    _ = app._load_or_generate_icon()
    assert icon_path.exists() is True

    # Verify ICO contains 256×256 frame.
    ico = Image.open(icon_path)
    sizes = set()
    for frame in range(getattr(ico, "n_frames", 1)):
        ico.seek(frame)
        sizes.add(ico.size)
    assert (256, 256) in sizes, "ICO missing high-DPI (256×256) asset"


def test_icon_reloads_on_dpi_change(tmp_path, monkeypatch):
    """TrayApp should call *update_icon* when system DPI jumps (Task 45.2)."""

    from InstanceScrubber import tray_app as tray_mod

    # Patch resource path to avoid writing into repo.
    monkeypatch.setattr(tray_mod, "resource_path", lambda rel: tmp_path / rel)

    # Replace *TrayApp._get_system_dpi* with custom iterator returning 96 → 144.
    dpi_iter = _cycle([96, 144])  # first call 96, second 144, then stable
    monkeypatch.setattr(tray_mod.TrayApp, "_get_system_dpi", staticmethod(lambda: next(dpi_iter)))

    # Shrink check interval for faster test (~10 ms).
    monkeypatch.setattr(tray_mod.TrayApp, "_DPI_CHECK_INTERVAL", 0.01)

    # Callbacks (no-op)
    app = tray_mod.TrayApp(_DummyConfig(), lambda: None, lambda: None)
    assert app.start() is True

    # Allow background thread a moment to detect DPI change.
    time.sleep(0.05)

    # Verify stub received *update_icon*.
    assert isinstance(app._icon, _StubIcon)
    assert app._icon.icon_updated is True, "Expected update_icon after DPI change"

    app.stop() 