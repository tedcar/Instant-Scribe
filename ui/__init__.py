# --- UI domain package ------------------------------------------------------
"""User-interface helpers (tray / notifications) for Instant Scribe.

The legacy *InstanceScrubber* implementation shipped all UI related code in
individual top-level modules.  This package provides a cohesive namespace for
those classes while delegating to the original modules under the hood.

Example::

    from ui import TrayApp, NotificationManager
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Final

_legacy_map: dict[str, str] = {
    "TrayApp": "InstanceScrubber.tray_app.TrayApp",
    "NotificationManager": "InstanceScrubber.notification_manager.NotificationManager",
}

__all__: list[str] = list(_legacy_map.keys())


class _LazyAttr:  # pylint: disable=too-few-public-methods
    def __init__(self, path: str) -> None:
        self._path: Final[str] = path
        self._target: Any | None = None

    def _resolve(self):  # noqa: D401 – internal
        if self._target is None:
            mod, _, attr = self._path.rpartition(".")
            self._target = getattr(import_module(mod), attr)
        return self._target

    def __getattr__(self, name):  # noqa: D401 – proxy attributes
        return getattr(self._resolve(), name)

    def __call__(self, *args, **kwargs):  # noqa: D401 – proxy callables
        return self._resolve()(*args, **kwargs)


globals().update({k: _LazyAttr(v) for k, v in _legacy_map.items()}) 