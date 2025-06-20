from __future__ import annotations

"""Typed dataclass messages passed between processes.

Using `dataclass` ensures the payload is pickleable by the `multiprocessing`
backend while still providing a type‐safe interface for the rest of the
application code.
"""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

__all__ = [
    "Message",
    "Transcribe",
    "Shutdown",
    "UnloadModel",
    "LoadModel",
    "Response",
]

_T = TypeVar("_T")


@dataclass(slots=True)
class Message:
    """Base‐class for all IPC messages."""


@dataclass(slots=True)
class Transcribe(Message):
    """Request for the worker to transcribe a buffer of audio."""

    audio: bytes  # Raw PCM or encoded audio buffer


@dataclass(slots=True)
class Shutdown(Message):
    """Signal the worker to perform a graceful shutdown."""

    reason: str | None = None


@dataclass(slots=True)
class UnloadModel(Message):
    """Request the worker to *unload* the ASR model from VRAM."""


@dataclass(slots=True)
class LoadModel(Message):
    """Request the worker to (re)-load the ASR model into VRAM."""


@dataclass(slots=True)
class Response(Generic[_T], Message):
    """Generic response wrapper returned from the worker process."""

    result: _T
    """Result payload – for a *Transcribe* request this will usually be the
    transcription text or richer metadata depending on the worker API.
    """ 