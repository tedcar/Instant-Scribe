from __future__ import annotations

"""Global hotkey registration wrapper (Task 7 – DEV_TASKS.md).

This module provides a thin layer around the *keyboard* package to:

1. Register a global hotkey defined in :class:`InstanceScrubber.config_manager.ConfigManager`.
2. Expose *start* / *stop* helpers for predictable lifecycle management.
3. Support *reload()* to pick up changes to the hotkey string at runtime.
4. Detect registration conflicts or other failures and log a warning rather
   than raising, keeping the app resilient when the keyboard hook cannot be
   installed (for example in CI or headless sessions).

The implementation purposefully avoids importing *keyboard* at module level to
allow unit-tests to stub the library before the first import, and to avoid
import-time side-effects when the host system blocks the underlying hooks.
"""

import logging
from typing import Callable, Optional

__all__ = ["HotkeyManager"]


class HotkeyManager:  # pylint: disable=too-few-public-methods
    """Register and manage a single global hotkey.

    Parameters
    ----------
    config_manager
        Instance of :class:`InstanceScrubber.config_manager.ConfigManager` (or
        any duck-typed alternative exposing *get()* / *set()* / *reload()*).
    on_activate
        Callback invoked when the hotkey is pressed.
    suppress
        If *True*, the hotkey combination is suppressed system-wide (see
        keyboard.add_hotkey docs).  Defaults to *False* so that the
        combination still reaches the active window unless explicitly required
        otherwise by the UI layer.
    """

    def __init__(
        self,
        config_manager,
        on_activate: Callable[[], None],
        *,
        suppress: bool = False,
    ) -> None:
        self._config = config_manager
        self._callback = on_activate
        self._suppress = suppress

        self._hotkey_handle: Optional[str | int] = None
        self._current_hotkey: Optional[str] = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def start(self) -> bool:  # noqa: D401 – imperative API
        """Register the global hotkey.

        Returns *True* when registration succeeds, *False* otherwise.
        """

        if self._hotkey_handle is not None:
            logging.debug("HotkeyManager already running – start() ignored")
            return True

        hotkey = str(self._config.get("hotkey", "ctrl+alt+f"))
        try:
            import keyboard  # local import keeps startup fast & mock-friendly

            self._hotkey_handle = keyboard.add_hotkey(
                hotkey,
                self._callback,
                suppress=self._suppress,
            )
            self._current_hotkey = hotkey
            logging.info("Registered global hotkey: %s", hotkey)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            # Any failure (unsupported platform, permission error, duplicate)
            # is logged but does not crash the application.
            logging.warning("Failed to register hotkey '%s': %s", hotkey, exc)
            self._hotkey_handle = None
            self._current_hotkey = None
            return False

    def stop(self) -> None:  # noqa: D401 – imperative API
        """Unregister the hotkey if currently active."""
        if self._hotkey_handle is None:
            return
        try:
            import keyboard  # import here to match *start()* locality

            keyboard.remove_hotkey(self._hotkey_handle)
            logging.info("Unregistered global hotkey: %s", self._current_hotkey)
        except Exception as exc:  # pylint: disable=broad-except
            logging.debug("Ignoring error while removing hotkey: %s", exc)
        finally:
            self._hotkey_handle = None
            self._current_hotkey = None

    def reload(self) -> bool:  # noqa: D401 – imperative API
        """Reload configuration and update the hotkey if it changed.

        Returns *True* if the reload succeeds (or if no change was required).
        Returns *False* if registration of the *new* hotkey failed (the old
        one will have been unregistered in that case).
        """

        # Ensure we have the latest config from disk.
        try:
            self._config.reload()  # type: ignore[attr-defined]
        except AttributeError:
            # Duck-type configs used in tests may not implement *reload()*.
            pass

        new_hotkey = str(self._config.get("hotkey", "ctrl+alt+f"))
        if new_hotkey == self._current_hotkey:
            logging.debug("Hotkey unchanged (%s) – reload() no-op", new_hotkey)
            return True

        # Apply the change: remove old & register new.
        self.stop()
        return self.start()

    # ------------------------------------------------------------------
    # Convenience dunders
    # ------------------------------------------------------------------
    def __enter__(self):  # noqa: D401 – context manager for with-statement
        if not self.start():
            raise RuntimeError("Unable to register global hotkey")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: D401 – context manager
        self.stop()
        # Do not suppress exceptions – propagate to caller.
        return False 