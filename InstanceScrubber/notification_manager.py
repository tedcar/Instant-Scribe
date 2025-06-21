from __future__ import annotations

"""Cross-platform notification helper for Instant Scribe.

The implementation uses the **windows-toasts** package to display native
Windows 10/11 toast notifications.  When the runtime platform does not
support WinRT – or the package is missing – the manager degrades
gracefully by logging the message instead of raising.

Core features (Task 9):
    • show a *Transcription complete* toast containing the recognised text
    • clicking the toast copies the full transcription to the clipboard
      (powered by :pymod:`pyperclip`)
    • fallback path that avoids hard dependency on WinRT
"""

from typing import Callable, Optional
import logging

# ---------------------------------------------------------------------------
# Optional Windows-specific dependencies
# ---------------------------------------------------------------------------
try:
    # Importing may succeed on non-Windows but runtime calls could still fail.
    from windows_toasts import Toast, WindowsToaster  # type: ignore

    _WINRT_IMPORT_SUCCESS = True
except Exception as exc:  # pragma: no cover – not an error, we fall back
    logging.getLogger(__name__).info("Windows toast notifications unavailable: %s", exc)
    Toast = None  # type: ignore[assignment]
    WindowsToaster = None  # type: ignore[assignment]
    _WINRT_IMPORT_SUCCESS = False

import pyperclip  # Copy-to-clipboard backend (cross-platform)

__all__ = ["NotificationManager"]


class NotificationManager:  # pylint: disable=too-few-public-methods
    """Runtime helper responsible for user-visible notifications."""

    #: Default title shown for finished transcriptions
    _DEFAULT_TITLE = "Transcription complete"

    def __init__(
        self,
        app_name: str = "Instant Scribe",
        *,
        copy_on_click: bool | None = None,
        show_notifications: bool | None = None,
    ) -> None:
        """Create a new *NotificationManager*.

        Parameters
        ----------
        app_name
            Friendly application name displayed by Windows.
        copy_on_click
            Whether to copy toast contents to clipboard when the user clicks
            the notification.  If *None* the value will later be interrogated
            from :class:`InstanceScrubber.config_manager.ConfigManager`.
        show_notifications
            Master on/off switch.  When *False*, no attempt is made to display
            UI toasts even if **windows-toasts** is installed.  *None* defers
            the decision to run-time configuration.
        """

        self._log = logging.getLogger(self.__class__.__name__)
        self._app_name = app_name
        self._copy_on_click_default = copy_on_click
        self._show_notifications_default = show_notifications

        # Attempt to instantiate the WinRT bridge if available.
        self._toaster: Optional["WindowsToaster"]
        if _WINRT_IMPORT_SUCCESS and show_notifications is not False:
            try:
                # WindowsToaster may still raise if underlying WinRT APIs are
                # inaccessible (e.g., running under Wine or Linux CI).
                self._toaster = WindowsToaster(app_name)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover – runtime environment
                self._log.info("Disabling toast support – runtime error: %s", exc)
                self._toaster = None
        else:
            self._toaster = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def show_transcription(self, text: str, *, copy_to_clipboard: bool | None = None) -> None:
        """Display a *transcription complete* notification.

        When the user clicks the toast (provided the platform supports it),
        the *text* is re-copied to the clipboard for convenience.
        """

        # Decide clipboard behaviour – explicit param takes precedence over ctor default
        copy_enabled = (
            copy_to_clipboard
            if copy_to_clipboard is not None
            else (self._copy_on_click_default if self._copy_on_click_default is not None else True)
        )

        # Always attempt to copy immediately – even if notifications are disabled.
        if copy_enabled:
            self._copy_to_clipboard(text)

        if not self._toaster:
            # Headless / unsupported environment – log and bail out.
            self._log.debug("Toast suppressed (not supported). Body: %s", text)
            return

        # --- Prepare the toast ------------------------------------------------
        if Toast is None:
            # Fallback: create a minimal stub compatible with the attributes
            # accessed below.  This path is exercised by the unit-tests which
            # monkey-patch *self._toaster* with a fake in-memory implementation
            # but intentionally skip providing a global *Toast* symbol.
            class _StubToast:  # pylint: disable=too-few-public-methods
                def __init__(self):
                    self.text_fields = []
                    self.on_activated: Callable[[], None] | None = None  # noqa: D401

            toast = _StubToast()  # type: ignore[assignment]
        else:
            toast = Toast()  # type: ignore[call-arg]
        toast.text_fields = [self._DEFAULT_TITLE, text]

        if copy_enabled:
            toast.on_activated = lambda: self._copy_to_clipboard(text)

        # --- Display ----------------------------------------------------------
        try:
            self._toaster.show_toast(toast)  # type: ignore[arg-type]
            self._log.debug("Toast shown successfully")
        except Exception as exc:  # pragma: no cover – runtime path
            # Do *not* raise – silently degrade to logfile only.
            self._log.warning("Failed to display toast: %s", exc)

    # ------------------------------------------------------------------
    # VRAM toggle helpers (Task 11)
    # ------------------------------------------------------------------

    def show_model_state(self, state: str) -> None:  # noqa: D401 – imperative API
        """Display a toast reflecting the current *model VRAM* state.

        Parameters
        ----------
        state
            Either ``"loaded"`` or ``"unloaded"``.  Any other string will be
            passed through verbatim.
        """

        title = "Instant Scribe"
        message = (
            "Model loaded and ready." if state == "loaded" else "Model unloaded from VRAM."
            if state == "unloaded" else str(state)
        )

        if not self._toaster:
            self._log.debug("Toast suppressed (not supported). Body: %s", message)
            return

        # Re-use the same fallback factory used in *show_transcription* to
        # keep behaviour consistent and test-friendly.
        if Toast is None:
            class _StubToast:  # pylint: disable=too-few-public-methods
                def __init__(self):
                    self.text_fields = []

            toast = _StubToast()  # type: ignore[assignment]
        else:
            toast = Toast()  # type: ignore[call-arg]
        toast.text_fields = [title, message]

        try:
            self._toaster.show_toast(toast)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover – runtime path
            self._log.warning("Failed to display toast: %s", exc)

    # ------------------------------------------------------------------
    # Task 12 – crash recovery prompt
    # ------------------------------------------------------------------

    def show_recovery_prompt(self) -> None:  # noqa: D401 – imperative API
        """Inform the user that an incomplete recording was found on disk.

        The full interactive *Yes / No* prompt described in the Final Product
        Vision is beyond the scope of this initial implementation.  For now
        we display a simple informational toast so that manual recovery can
        be initiated via the ``--recover`` CLI flag.
        """

        title = "Instant Scribe – Recovery"
        message = "An incomplete recording was found.  Re-launch with --recover to resume."

        if not self._toaster:
            self._log.warning(message)
            return

        # Re-use the same fallback factory used in *show_transcription* to
        # keep behaviour consistent and test-friendly.
        if Toast is None:
            class _StubToast:  # pylint: disable=too-few-public-methods
                def __init__(self):
                    self.text_fields = []

            toast = _StubToast()  # type: ignore[assignment]
        else:
            toast = Toast()  # type: ignore[call-arg]
        toast.text_fields = [title, message]

        try:
            self._toaster.show_toast(toast)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover – runtime path
            self._log.warning("Failed to display toast: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _copy_to_clipboard(payload: str) -> None:
        """Copy *payload* to the system clipboard – with error suppression."""
        try:
            # Delegate the heavy lifting to the centralised helper (Task 23)
            from .clipboard_manager import copy_with_verification  # local import to avoid cycles

            if not copy_with_verification(payload):
                logging.getLogger(__name__).warning(
                    "Clipboard unavailable – payload written to fallback file instead",
                )
        except Exception as exc:  # pragma: no cover – unexpected runtime error
            logging.getLogger(__name__).warning("Clipboard handling failed: %s", exc) 