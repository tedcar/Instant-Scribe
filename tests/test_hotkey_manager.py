import inspect
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so local imports work when running via `python -m pytest` from subdir
import sys
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.hotkey_manager import HotkeyManager  # noqa: E402


class _StubKeyboard:
    """Stub replacement for the *keyboard* module used in tests."""

    def __init__(self, *, raise_on_add: bool = False):
        self.registered = []  # list of (hotkey, callback)
        self.removed = []  # list of handles removed
        self._next_handle = 1
        self._raise = raise_on_add

    # pylint: disable=unused-argument
    def add_hotkey(self, hotkey, callback, *, suppress=False):  # noqa: D401 – stub signature
        if self._raise:
            raise RuntimeError("registration failed (simulated)")
        handle = self._next_handle
        self._next_handle += 1
        self.registered.append((hotkey, callback, suppress))
        return handle

    def remove_hotkey(self, handle):  # noqa: D401 – stub
        self.removed.append(handle)


class _DummyConfig:
    """Minimal config manager stub supporting get / set / reload."""

    def __init__(self, hotkey: str = "ctrl+alt+f"):
        self._data = {"hotkey": hotkey}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value, *, auto_save=True):  # noqa: D401 – signature match
        self._data[key] = value

    def reload(self):  # noqa: D401 – no-op for tests
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_hotkey_registration(monkeypatch):
    """start() should register the hotkey specified in the config."""
    stub_keyboard = _StubKeyboard()
    monkeypatch.setitem(sys.modules, "keyboard", stub_keyboard)

    cfg = _DummyConfig("ctrl+alt+g")
    events = {
        "triggered": False,
    }

    def _cb():
        events["triggered"] = True

    manager = HotkeyManager(cfg, _cb)
    assert manager.start() is True
    assert stub_keyboard.registered[0][0] == "ctrl+alt+g"


def test_hotkey_reload(monkeypatch):
    """reload() should re-register when the hotkey string changes."""
    stub_keyboard = _StubKeyboard()
    monkeypatch.setitem(sys.modules, "keyboard", stub_keyboard)

    cfg = _DummyConfig("ctrl+alt+a")
    manager = HotkeyManager(cfg, lambda: None)
    manager.start()

    # Update config and ensure reload triggers remove & add sequence
    cfg.set("hotkey", "ctrl+shift+z")
    manager.reload()

    # The stub should have exactly two registrations and one removal
    assert stub_keyboard.registered[0][0] == "ctrl+alt+a"
    assert stub_keyboard.registered[1][0] == "ctrl+shift+z"
    assert stub_keyboard.removed == [1]  # first handle removed


def test_hotkey_conflict(monkeypatch):
    """If add_hotkey raises an exception the method returns False."""
    stub_keyboard = _StubKeyboard(raise_on_add=True)
    monkeypatch.setitem(sys.modules, "keyboard", stub_keyboard)

    cfg = _DummyConfig("ctrl+alt+p")
    manager = HotkeyManager(cfg, lambda: None)
    assert manager.start() is False
    # No registrations should have succeeded
    assert stub_keyboard.registered == [] 