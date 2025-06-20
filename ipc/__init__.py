from __future__ import annotations

"""Inter-process communication helpers for Instant Scribe.

This package provides typed messages and queue helper utilities used by the
main application and the transcription worker process.  Keeping the IPC layer
in a dedicated top-level package avoids pickle import-path issues when using
``multiprocessing.set_start_method('spawn')`` on Windows.
"""

# Export public symbols so ``from ipc import *`` exposes them.
from .messages import Message, Transcribe, Shutdown, Response  # noqa: F401
from .queue_wrapper import IPCQueue  # noqa: F401 