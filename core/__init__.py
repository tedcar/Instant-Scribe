# --- Core domain package ----------------------------------------------------
"""Shared *core* helpers for Instant Scribe.

The sub-package gathers foundational, **non-UI** utilities such as
configuration, logging, persistence and archival helpers.  To maintain
100 % backwards-compatibility the implementations are re-exported from the
original *InstanceScrubber* modules (and their sibling *instant_scribe*
modules where applicable).

Typical usage::

    from core import ConfigManager, ResourceManager
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Final

# ---------------------------------------------------------------------------
# Dynamically import and re-export symbols
# ---------------------------------------------------------------------------

_legacy_map: dict[str, str] = {
    # key = public symbol, value = fully-qualified legacy dotted path
    "ConfigManager": "InstanceScrubber.config_manager.ConfigManager",
    "setup_logging": "InstanceScrubber.logging_config.setup_logging",
    "resource_path": "InstanceScrubber.resource_manager.resource_path",
    "ArchiveManager": "InstanceScrubber.archive_manager.ArchiveManager",
    "ArchiveBackup": "InstanceScrubber.archive_backup.ArchiveBackup",
    "Spooler": "InstanceScrubber.spooler.Spooler",
    "TranscriptionWorker": "InstanceScrubber.transcription_worker.TranscriptionWorker",
}

__all__: list[str] = list(_legacy_map.keys())  # exported public API

# Perform *lazy* imports so that optional heavy dependencies (e.g. torch)
# are only initialised when clients actually access the symbols.

class _LazyModuleAttr:  # pylint: disable=too-few-public-methods
    def __init__(self, fq_name: str) -> None:
        self._fq_name: Final[str] = fq_name
        self._target: Any | None = None

    def _resolve(self) -> Any:  # noqa: D401 – internal helper
        if self._target is None:
            module_name, _, attr_name = self._fq_name.rpartition(".")
            module = import_module(module_name)
            self._target = getattr(module, attr_name)
        return self._target

    def __getattr__(self, item):  # noqa: D401 – delegate to resolved target
        return getattr(self._resolve(), item)

    def __call__(self, *args, **kwargs):  # noqa: D401 – proxy callable
        return self._resolve()(*args, **kwargs)


globals().update({name: _LazyModuleAttr(path) for name, path in _legacy_map.items()}) 