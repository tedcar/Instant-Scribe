import types
import inspect
from pathlib import Path
import sys

# Ensure repo root on sys.path for import resolution
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

# ---------------------------------------------------------------------------
# Create an in-memory stub for the *windows_toasts* dependency so the tests can
# run on Linux/macOS CI runners that lack WinRT APIs.
# ---------------------------------------------------------------------------

class _FakeToast:  # pylint: disable=too-few-public-methods
    """Minimal stub mirroring the interface used by NotificationManager."""

    def __init__(self):
        self.text_fields = []
        self.on_activated = None


class _FakeToaster:  # pylint: disable=too-few-public-methods
    def __init__(self, app_name: str):  # noqa: D401 – simple stub
        self.app_name = app_name
        self.shown = []  # type: list[_FakeToast]

    def show_toast(self, toast):  # noqa: ANN001 – external interface
        self.shown.append(toast)


# Inject the fake module **before** importing the SUT so the *import* in the
# target module succeeds.
fake_mod = types.ModuleType("windows_toasts")
fake_mod.Toast = _FakeToast  # type: ignore[attr-defined]
fake_mod.WindowsToaster = _FakeToaster  # type: ignore[attr-defined]
sys.modules["windows_toasts"] = fake_mod

# Now the import should pick up our stubbed implementation.
from InstanceScrubber.notification_manager import NotificationManager  # noqa: E402
import pyperclip  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_clipboard(monkeypatch):
    """Intercept :pyfunc:`pyperclip.copy` to avoid touching the system clipboard."""
    clipboard: dict[str, str] = {}

    def fake_copy(payload: str):  # noqa: D401 – simple stub
        clipboard["data"] = payload

    monkeypatch.setattr(pyperclip, "copy", fake_copy)
    return clipboard


def test_toast_shown_and_copied(_isolate_clipboard):
    """Calling *show_transcription* should display a toast and copy text."""
    manager = NotificationManager(app_name="TestApp")

    # Ensure we use the stub toaster regardless of whether the real WinRT
    # backend is available on the test host.
    manager._toaster = _FakeToaster("TestApp")  # type: ignore[attr-defined]

    sample_text = "Hello world"
    manager.show_transcription(sample_text)

    # The fake toaster instance should have registered a single toast
    toaster: _FakeToaster = manager._toaster  # type: ignore[attr-defined]
    assert toaster is not None and len(toaster.shown) == 1

    toast = toaster.shown[0]
    # Toast should contain both title and body
    assert sample_text in toast.text_fields

    # Clipboard should have received the payload
    assert _isolate_clipboard["data"] == sample_text


def test_copy_disabled(_isolate_clipboard):
    """Explicitly disabling *copy_to_clipboard* should skip clipboard call."""
    manager = NotificationManager(app_name="TestApp")

    manager.show_transcription("No copy", copy_to_clipboard=False)

    # Clipboard dict should remain empty
    assert "data" not in _isolate_clipboard


def test_no_toast_backend(monkeypatch):
    """If WinRT backend is unavailable, the call should not raise."""
    # Force the internal _toaster attribute to None to simulate headless mode.
    manager = NotificationManager(app_name="Headless", show_notifications=False)
    assert manager._toaster is None  # type: ignore[attr-defined]

    # Should execute silently without throwing.
    manager.show_transcription("Hello") 