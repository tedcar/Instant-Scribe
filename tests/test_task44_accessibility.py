import importlib
import sys
from pathlib import Path

import pytest

from InstanceScrubber.config_manager import ConfigManager

# ---------------------------------------------------------------------------
# Helper stubs for the *windows_toasts* package so the tests do not depend on
# a Windows environment.  They must be inserted **before** NotificationManager
# is imported to override the optional import attempt performed at module load.
# ---------------------------------------------------------------------------

class _FakeToast:  # pylint: disable=too-few-public-methods
    def __init__(self):
        self.text_fields = []
        self.attribution_text = None
        self.on_activated = None


class _FakeToaster:
    def __init__(self, _app_name: str):
        self.shown_toast = None

    def show_toast(self, toast):  # noqa: D401 – external API shape
        self.shown_toast = toast


@pytest.fixture(autouse=True)
def _patch_windows_toasts(monkeypatch):
    """Ensure *InstanceScrubber.notification_manager* imports succeed.

    The module tries to import *windows_toasts* eagerly.  We monkey-patch the
    dependency in *sys.modules* before the import occurs so that the real
    (Windows-only) package is never required.
    """
    fake_pkg = type(sys)("windows_toasts")
    fake_pkg.Toast = _FakeToast  # type: ignore[attr-defined]
    fake_pkg.WindowsToaster = _FakeToaster  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "windows_toasts", fake_pkg)

    # Stub heavy optional dependencies imported transitively by the package
    for _mod in ("numpy", "torch", "nemo", "nemo.collections", "nemo.collections.asr", "pyperclip"):
        monkeypatch.setitem(sys.modules, _mod, importlib.import_module("types").ModuleType(_mod))

    # Provide a minimal stub for Pillow when the real package is absent.  Only
    # the *Image* class constructor is required by *TrayApp* placeholder logic.
    if "PIL" not in sys.modules:
        from types import ModuleType

        pil_stub = ModuleType("PIL")
        image_module = ModuleType("PIL.Image")
        # Minimal *Image* stand-in storing size attribute accessed by tests
        class _FakeImage:  # pylint: disable=too-few-public-methods
            def __init__(self, size=(64, 64)):
                self._size = size

            @property
            def size(self):  # noqa: D401 – simple property
                return self._size

            def save(self, *_args, **_kwargs):  # noqa: D401 – no-op
                pass

        image_module.Image = _FakeImage  # type: ignore[attr-defined]
        # Expose factory returning fake image when called as constructor
        def _new(*args, **kwargs):  # noqa: D401 – mimic PIL.Image.new
            return _FakeImage(kwargs.get("size", (64, 64)))

        image_module.new = _new  # type: ignore[attr-defined]

        pil_stub.Image = image_module  # type: ignore[attr-defined]

        # Add minimal ImageDraw and ImageFont sub-modules expected by TrayApp
        draw_module = ModuleType("PIL.ImageDraw")

        class _FakeDraw:  # pylint: disable=too-few-public-methods
            def __init__(self, *_args, **_kwargs):
                pass

            def ellipse(self, *_args, **_kwargs):  # noqa: D401 – no-op
                pass

            def text(self, *_args, **_kwargs):  # noqa: D401 – no-op
                pass

            def textsize(self, text, font=None):  # noqa: D401 – return dummy size
                return (len(str(text)) * 6, 10)

        draw_module.Draw = lambda img: _FakeDraw()  # type: ignore[attr-defined]

        font_module = ModuleType("PIL.ImageFont")

        class _FakeFont:  # pylint: disable=too-few-public-methods
            pass

        font_module.load_default = lambda: _FakeFont()  # type: ignore[attr-defined]

        pil_stub.ImageDraw = draw_module  # type: ignore[attr-defined]
        pil_stub.ImageFont = font_module  # type: ignore[attr-defined]
        # Insert both *PIL* and *PIL.Image* into *sys.modules*
        monkeypatch.setitem(sys.modules, "PIL", pil_stub)
        monkeypatch.setitem(sys.modules, "PIL.Image", image_module)
        monkeypatch.setitem(sys.modules, "PIL.ImageDraw", draw_module)
        monkeypatch.setitem(sys.modules, "PIL.ImageFont", font_module)

    yield
    # Clean up to avoid leaking into other tests
    monkeypatch.setitem(sys.modules, "windows_toasts", None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_tray_icon_high_contrast(monkeypatch, tmp_path):
    """TrayApp should generate & use a high-contrast icon when configured."""

    # Point ConfigManager to a temporary location to avoid polluting user dirs
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg = ConfigManager()
    cfg.set("high_contrast_icons", True)

    # Lazy import to pick up monkey-patches applied above
    from InstanceScrubber.tray_app import TrayApp
    from PIL import Image  # type: ignore  # import after stubs in fixture

    app = TrayApp(cfg, lambda: None, lambda: None)

    # Call the private helper directly – GUI can't run in CI environment
    img = app._load_or_generate_icon()  # pylint: disable=protected-access

    # The image should be PIL.Image and non-empty
    assert isinstance(img, Image.Image)
    assert img.size[0] > 0 and img.size[1] > 0

    # The generated ICO file should now exist on disk with HC path
    hc_path = app._get_icon_path()  # pylint: disable=protected-access
    assert hc_path.exists(), "High-contrast icon should have been created"


def test_notification_accessibility(monkeypatch):
    """NotificationManager must include *attribution_text* for screen readers."""

    # Re-import the module after we patched *windows_toasts* so the constants
    # referencing the fake package are initialised correctly.
    nm = importlib.reload(importlib.import_module("InstanceScrubber.notification_manager"))

    mgr = nm.NotificationManager(app_name="TestApp", show_notifications=True)

    # Replace the internally stored toaster with our fake implementation
    fake_toaster = _FakeToaster("TestApp")
    mgr._toaster = fake_toaster  # type: ignore[attr-defined]  # pylint: disable=protected-access

    mgr.show_transcription("Hello world")

    # Ensure a toast was captured and the accessibility field is populated
    toast = fake_toaster.shown_toast
    assert toast is not None, "Toast should have been shown via fake toaster"
    assert getattr(toast, "attribution_text", None) == "Transcription complete"