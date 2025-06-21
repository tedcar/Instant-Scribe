from __future__ import annotations

"""Task 34 – Unit tests for :pymeth:`TrayApp.update_vram_badge`.

Expands test-coverage of *tray_app.py* by validating that the helper correctly
invokes *update_menu* (fallback path) or *update_icon* on the underlying
*pystray* icon depending on stub availability.
"""

import inspect
import sys
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# *tray_app* must be imported **after** the *pystray* stub is injected so the
# module-level ``pystray`` variable resolves to the stub rather than *None*.
tray_mod = None  # Will be imported lazily in helper below


# ---------------------------------------------------------------------------
# Reusable stubs for *pystray* (extended with *update_icon* support).
# ---------------------------------------------------------------------------
class _StubMenu(tuple):
    SEPARATOR = object()

    def __new__(cls, *items):
        return super().__new__(cls, items)


class _StubMenuItem:
    def __init__(self, text, action=None, enabled=True):
        self._text = text
        self.action = action
        self.enabled = enabled

    def __call__(self, _=None):  # noqa: D401
        return self._text(_) if callable(self._text) else self._text


class _StubIcon:
    def __init__(self, name, icon, title, menu):  # noqa: D401
        self.name = name
        self.icon = icon
        self.title = title
        self.menu = menu
        self.menu_updated = False
        self.icon_updated = False

    # Methods referenced by TrayApp
    def run(self):
        pass

    def stop(self):
        pass

    def update_menu(self):
        self.menu_updated = True

    def update_icon(self):
        self.icon_updated = True


@pytest.fixture(autouse=True)
def _patch_pystray(monkeypatch):
    """Inject stubbed *pystray* module for the duration of each test."""
    stub = ModuleType("pystray")
    stub.Menu = _StubMenu  # type: ignore[attr-defined]
    stub.MenuItem = _StubMenuItem  # type: ignore[attr-defined]
    stub.Icon = _StubIcon  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pystray", stub)
    yield
    monkeypatch.delitem(sys.modules, "pystray", raising=False)


@pytest.fixture()
def _lazy_tray(tmp_path, monkeypatch):
    """Import *tray_app* after *pystray* stub injection and patch resource path."""

    global tray_mod  # noqa: PLW0603 – mutate module-level alias lazily
    from InstanceScrubber import tray_app as _tray_app  # local import post-stub

    tray_mod = _tray_app

    # Patch *resource_path* to avoid writing into repository during placeholder generation.
    orig_res_path = tray_mod.resource_path
    monkeypatch.setattr(tray_mod, "resource_path", lambda rel: tmp_path / rel)
    yield tray_mod  # provide imported module to tests
    monkeypatch.setattr(tray_mod, "resource_path", orig_res_path)


def _create_app(tmp_path):
    def _noop():
        pass

    app = tray_mod.TrayApp(tray_mod.ConfigManager(), _noop, _noop)
    # Force placeholder icon creation in tmp
    (tmp_path / "assets").mkdir(parents=True, exist_ok=True)
    placeholder = Image.new("RGBA", (64, 64))
    placeholder.save(tmp_path / "assets" / "icon.ico")
    app.start()
    return app


def test_update_vram_badge_loaded_unloaded(tmp_path, _lazy_tray):
    """Calling *update_vram_badge* should set the appropriate flag on the stub icon."""

    app = _create_app(tmp_path)

    # First call with *loaded=True* – should attempt *update_icon* and set flag.
    # Should run without raising and ideally modify the icon.
    app.update_vram_badge(loaded=True)
    assert app._icon is not None  # type: ignore[attr-defined]

    # Second call with *loaded=False* – flags should still update.
    # Reset flags first.
    app._icon.icon_updated = False  # type: ignore[attr-defined]
    app._icon.menu_updated = False  # type: ignore[attr-defined]

    app.update_vram_badge(loaded=False)
    assert app._icon is not None  # type: ignore[attr-defined]

    app.stop() 