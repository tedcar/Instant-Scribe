import inspect
import sys
from pathlib import Path
from types import ModuleType

import pytest

# ---------------------------------------------------------------------------
# Ensure repository root is on *sys.path* so local imports resolve irrespective
# of where `pytest` is invoked from.
# ---------------------------------------------------------------------------
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# ---------------------------------------------------------------------------
# Lightweight *pystray* stub – allows running tests in headless CI containers
# without the real GTK / Win32 back-end bindings.
# ---------------------------------------------------------------------------
class _StubMenu(tuple):
    """Tuple subclass mimicking :class:`pystray.Menu`."""

    SEPARATOR = object()

    def __new__(cls, *items):
        return super().__new__(cls, items)


class _StubMenuItem:
    """Very small placeholder for :class:`pystray.MenuItem`."""

    def __init__(self, text, action=None, enabled=True):
        self._text = text  # may be callable for dynamic entries
        self.action = action
        self.enabled = enabled

    # pystray calls the *text* callable to get label at render-time
    def __call__(self, _=None):  # noqa: D401 – emulate str behaviour
        return self._text(_) if callable(self._text) else self._text


class _StubIcon:
    """Headless replacement for :class:`pystray.Icon`."""

    def __init__(self, name, icon, title, menu):  # noqa: D401 – signature match
        self.name = name
        self.icon = icon
        self.title = title
        self.menu = menu
        self._running = False
        self.updated = False

    # ------------------------------------------------------------------
    # API surface used by *TrayApp*
    # ------------------------------------------------------------------
    def run(self):  # noqa: D401 – stub (no GUI loop)
        self._running = True

    def stop(self):  # noqa: D401 – stub
        self._running = False

    def update_menu(self):  # noqa: D401 – stub
        self.updated = True


@pytest.fixture(autouse=True)
def _patch_pystray(monkeypatch):
    """Replace the *pystray* module with stubs for the duration of each test."""

    stub = ModuleType("pystray")
    stub.Menu = _StubMenu  # type: ignore[attr-defined]
    stub.MenuItem = _StubMenuItem  # type: ignore[attr-defined]
    stub.Icon = _StubIcon  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pystray", stub)
    yield  # run test
    monkeypatch.delitem(sys.modules, "pystray", raising=False)


# ---------------------------------------------------------------------------
# Helper stubs for ConfigManager and callbacks
# ---------------------------------------------------------------------------
class _DummyConfig:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):  # noqa: D401 – stub
        return self.values.get(key, default)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_tray_app_menu_toggle(tmp_path):
    """Verify menu labels update and callbacks fire when toggling state."""
    # Redirect *resource_path* to *tmp_path* so placeholder icon doesn't pollute repo
    from InstanceScrubber import tray_app as tray_mod

    orig_resource_path = tray_mod.resource_path

    def _fake_res_path(rel):  # noqa: D401 – stub
        return tmp_path / rel

    tray_mod.resource_path = _fake_res_path  # type: ignore

    toggle_invoked = {"flag": False}

    def _toggle():
        toggle_invoked["flag"] = True

    exit_invoked = {"flag": False}

    def _exit():
        exit_invoked["flag"] = True

    app = tray_mod.TrayApp(_DummyConfig(), _toggle, _exit)
    assert app.start() is True

    # Initial status should be *Listening*
    status_item = app._icon.menu[0]  # type: ignore[attr-defined]
    assert status_item() == "Status: Listening"

    # Trigger toggle via menu callback
    toggle_item = app._icon.menu[2]  # type: ignore[attr-defined]
    toggle_item.action(app._icon, None)  # emulate user click

    assert toggle_invoked["flag"] is True
    assert app.is_listening is False
    # Menu should have been updated by TrayApp._on_toggle
    assert app._icon.updated is True
    assert status_item() == "Status: Idle"

    # Clean-up to avoid dangling threads
    app.stop()

    # Restore patched function
    tray_mod.resource_path = orig_resource_path 