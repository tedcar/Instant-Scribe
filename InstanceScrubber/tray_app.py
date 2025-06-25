from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

try:
    # Optional dependency – imported lazily to allow headless unit-testing with stubs.
    import pystray  # type: ignore
except ImportError:  # pragma: no cover – unit-tests replace *pystray* with a stub
    pystray = None  # type: ignore

from InstanceScrubber.config_manager import ConfigManager
from InstanceScrubber.resource_manager import resource_path

__all__ = ["TrayApp"]


class TrayApp:
    """Light-weight Windows *system-tray* UI wrapper using **pystray**.

    The tray icon exposes exactly the same runtime controls as the global
    hotkey handled by :class:`InstanceScrubber.hotkey_manager.HotkeyManager` –
    namely toggling the *listening* state and quitting the application.

    The implementation intentionally keeps *all* GUI-specific code isolated in
    order to remain importable – and therefore testable – in a headless CI
    environment (see ``tests/test_tray_app.py``).
    """

    _ICON_REL_PATH = "assets/icon.ico"
    _ICON_HIGH_CONTRAST_REL_PATH = "assets/icon_high_contrast.ico"

    # Task 45 – DPI monitoring interval (seconds)
    _DPI_CHECK_INTERVAL = 5.0

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def __init__(
        self,
        config: ConfigManager,
        on_toggle_listening: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self._cfg = config
        self._on_toggle_listening_cb = on_toggle_listening
        self._on_exit_cb = on_exit

        self._is_listening: bool = True  # initial state – matches HotkeyManager

        self._icon: "pystray.Icon | None" = None
        self._thread: threading.Thread | None = None

        # Task 45 – DPI monitoring
        self._current_dpi: int = self._get_system_dpi()
        self._dpi_monitor_thread: threading.Thread | None = None
        self._stop_dpi_monitoring = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> bool:
        """Create the :pymod:`pystray` icon and spin its event-loop *in a daemon
        thread* so the caller regains control immediately.
        """
        if pystray is None:
            logging.error("pystray not available – tray UI disabled")
            return False

        try:
            img = self._load_or_generate_icon()
            menu = self._build_menu()
            self._icon = pystray.Icon(
                name="Instant Scribe",
                title="Instant Scribe STT",
                icon=img,
                menu=menu,
            )
            # Run the icon loop in the background so unit-tests (and the main
            # application) can continue.
            self._thread = threading.Thread(target=self._icon.run, daemon=True)
            self._thread.start()

            # Task 45 – Start DPI monitoring
            self._start_dpi_monitoring()

            logging.info("System-tray icon started.")
            return True
        except Exception as exc:  # pragma: no cover – unexpected GUI failures
            logging.exception("Failed to start tray icon: %s", exc)
            return False

    def stop(self) -> None:
        """Gracefully stop the tray icon thread (if running)."""
        # Task 45 – Stop DPI monitoring
        self._stop_dpi_monitoring.set()
        if self._dpi_monitor_thread and self._dpi_monitor_thread.is_alive():
            self._dpi_monitor_thread.join(timeout=2)

        if self._icon:  # pragma: no branch – None check
            self._icon.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    # Expose read-only accessor for external components / tests
    @property
    def is_listening(self) -> bool:  # noqa: D401 – property style
        """Return *True* when the app is in *listening* state (green circle)."""
        return self._is_listening

    # ------------------------------------------------------------------
    # Implementation details
    # ------------------------------------------------------------------
    def _get_icon_path(self) -> Path:
        """Return the path to the icon file (high-contrast aware)."""
        use_high_contrast = self._cfg.get("high_contrast_icons", False)
        if use_high_contrast:
            return resource_path(self._ICON_HIGH_CONTRAST_REL_PATH)
        else:
            return resource_path(self._ICON_REL_PATH)

    def _load_or_generate_icon(self) -> Image.Image:
        """Return the PIL.Image used by the tray icon.

        The method first attempts to locate an *assets/icon.ico* file in the
        repository.  If the ICO is missing (common in fresh clones / CI
        environments) a very small placeholder is generated on-the-fly and
        persisted so subsequent runs can reuse it.

        Task 44: If high_contrast_icons is enabled, uses high-contrast variant.
        """
        # Task 44 – Use high-contrast aware path helper
        icon_path = self._get_icon_path()
        icon_path.parent.mkdir(parents=True, exist_ok=True)

        use_high_contrast = self._cfg.get("high_contrast_icons", False)

        if not icon_path.exists():
            logging.info("icon.ico not found – generating placeholder icon…")
            self._create_placeholder_icon(icon_path, high_contrast=use_high_contrast)

        # **pystray** accepts either a PIL.Image or an ICO *file path* – we use
        # the former to avoid file-handle lifetime issues on Windows.
        try:
            return Image.open(icon_path)
        except Exception as exc:  # pragma: no cover – filesystem issues
            logging.warning("Falling back to in-memory icon: %s", exc)
            return self._create_fallback_image(high_contrast=use_high_contrast)

    # ..................................................................
    # Menu & event handlers
    # ..................................................................
    def _build_menu(self) -> "pystray.Menu":
        # Import *inside* the method to let unit-tests inject stubs via
        # :pyfunc:`monkeypatch` *before* the real module is referenced.
        from pystray import Menu as _Menu, MenuItem as _Item  # type: ignore

        def _status_text(_: object) -> str:  # noqa: D401 – callback signature
            return f"Status: {'Listening' if self._is_listening else 'Idle'}"

        def _toggle_text(_: object) -> str:  # noqa: D401 – callback signature
            return "Stop Listening" if self._is_listening else "Start Listening"

        # The *enabled=False* attribute disables user interaction on the first
        # menu item (purely informational).
        return _Menu(
            _Item(_status_text, None, enabled=False),
            _Menu.SEPARATOR,
            _Item(_toggle_text, self._on_toggle),
            _Item("Exit", self._on_exit),
        )

    # ..................................................................
    # pystray callbacks (executed in icon thread)
    # ..................................................................
    def _on_toggle(self, icon, item):  # noqa: D401 – pystray signature
        # Flip local state **before** invoking external callback so the menu
        # reflects the new value when the callback finishes.
        self._is_listening = not self._is_listening
        try:
            self._on_toggle_listening_cb()
        finally:
            # Regardless of callback success ensure the UI updates.
            icon.update_menu()

    def _on_exit(self, icon, item):  # noqa: D401 – pystray signature
        try:
            self._on_exit_cb()
        finally:
            icon.stop()

    # ------------------------------------------------------------------
    # Helper graphics routines
    # ------------------------------------------------------------------
    def _create_placeholder_icon(self, out_path: Path, high_contrast: bool = False) -> None:
        """Generate a minimal .ico with *16×16*, *32×32*, and *256×256* assets.

        Task 44: Supports high-contrast mode (yellow on black).
        Task 45: Includes 256×256 for high-DPI displays.
        """
        # Task 45 – Create at largest size (256x256) so PIL can downscale properly
        img = self._create_fallback_image(size=256, high_contrast=high_contrast)
        # Task 45 – Include 256×256 for high-DPI displays
        sizes = [(16, 16), (32, 32), (256, 256)]
        img.save(out_path, format="ICO", sizes=sizes)

    def _create_fallback_image(self, size: int = 64, high_contrast: bool = False) -> Image.Image:
        """Return an in-memory circle placeholder *PIL.Image*.

        Task 44: Supports high-contrast mode (yellow on black background).
        """
        if high_contrast:
            # Task 44 – High-contrast: yellow on black
            bg_color = (0, 0, 0, 255)  # Black background
            circle_color = "#FFFF00"   # Yellow circle
            text_color = "black"       # Black text on yellow
        else:
            # Default: green on transparent
            bg_color = (0, 0, 0, 0)    # Transparent background
            circle_color = "#00AA00"   # Green circle
            text_color = "white"       # White text on green

        img = Image.new("RGBA", (size, size), bg_color)
        draw = ImageDraw.Draw(img)
        # Draw circle
        draw.ellipse([(4, 4), (size - 4, size - 4)], fill=circle_color)
        # Overlay *IS* text in the centre for quick visual ID
        try:
            font = ImageFont.load_default()
            text = "IS"
            w, h = draw.textsize(text, font=font)  # type: ignore[attr-defined]
            draw.text(((size - w) / 2, (size - h) / 2), text, font=font, fill=text_color)
        except Exception:  # pragma: no cover – font issues
            pass
        return img

    # ------------------------------------------------------------------
    # Task 33 – VRAM badge helper
    # ------------------------------------------------------------------
    def update_vram_badge(self, loaded: bool) -> None:  # noqa: D401 – imperative API
        """Set a small *green* (loaded) or *red* (unloaded) dot on the tray icon.

        The method attempts to update the icon *in-place* so the user receives
        immediate visual feedback when the ASR model is automatically unloaded
        due to low VRAM.
        """

        if pystray is None or self._icon is None:
            # Headless test environment – silently ignore.
            return

        try:
            base: Image.Image = self._icon.icon  # type: ignore[attr-defined]
        except AttributeError:
            base = self._load_or_generate_icon()

        # Draw a small circle in the bottom-right corner.
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        radius = base.size[0] // 8
        cx = base.size[0] - radius - 4
        cy = base.size[1] - radius - 4
        color = "#00AA00" if loaded else "#AA0000"
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], fill=color)

        combined = Image.alpha_composite(base.convert("RGBA"), overlay)
        self._icon.icon = combined  # type: ignore[attr-defined]
        try:
            self._icon.update_icon()  # pystray >=0.19 provides *update_icon*
        except Exception:
            # Fallback: recreate menu to force repaint (older pystray).
            try:
                self._icon.update_menu()
            except Exception:  # pragma: no cover – best effort
                pass

    # ------------------------------------------------------------------
    # Task 45 – High-DPI & Multi-Monitor Support
    # ------------------------------------------------------------------
    def _start_dpi_monitoring(self) -> None:
        """Start background thread to monitor DPI changes."""
        if self._dpi_monitor_thread is not None:
            return  # Already running

        self._dpi_monitor_thread = threading.Thread(
            target=self._dpi_monitor_loop,
            daemon=True
        )
        self._dpi_monitor_thread.start()

    def _dpi_monitor_loop(self) -> None:
        """Background loop that checks for DPI changes and reloads icon if needed."""
        # Use class attribute directly if it's been patched (for testing)
        interval = getattr(self.__class__, '_DPI_CHECK_INTERVAL', None)
        if interval is None:
            interval = self._cfg.get("dpi_check_interval_sec", 5.0)

        while not self._stop_dpi_monitoring.wait(interval):
            try:
                current_dpi = self._get_system_dpi()
                if current_dpi != self._current_dpi:
                    logging.info(f"DPI change detected: {self._current_dpi} → {current_dpi}")
                    self._current_dpi = current_dpi
                    self._reload_icon()
            except Exception as exc:  # pragma: no cover – defensive
                logging.debug("DPI monitoring error: %s", exc)

    def _reload_icon(self) -> None:
        """Reload the tray icon (called when DPI changes)."""
        if self._icon is None:
            return

        try:
            new_img = self._load_or_generate_icon()
            self._icon.icon = new_img  # type: ignore[attr-defined]
            self._icon.update_icon()  # pystray >=0.19 provides *update_icon*
        except Exception as exc:  # pragma: no cover – defensive
            logging.debug("Icon reload failed: %s", exc)

    @staticmethod
    def _get_system_dpi() -> int:
        """Return the current system DPI setting.

        Task 45: Used to detect DPI changes and trigger icon reloads.
        """
        try:
            # Try Windows-specific approach first
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()

            # Get DPI for the primary monitor
            hdc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            user32.ReleaseDC(0, hdc)

            return dpi if dpi > 0 else 96  # Default to 96 DPI
        except Exception:  # pragma: no cover – fallback for non-Windows
            return 96  # Standard DPI fallback