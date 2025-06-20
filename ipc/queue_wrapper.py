from __future__ import annotations

"""Thin wrapper around :pyclass:`multiprocessing.Queue` with timeout handling.

The standard queue raises :class:`queue.Empty` and :class:`queue.Full` which are
fairly generic.  This wrapper normalises them to :class:`TimeoutError` so that
callers can handle both put/get timeouts via a single exception type.
"""

import multiprocessing as _mp
import queue as _queue
from typing import Generic, TypeVar

_T = TypeVar("_T")


class IPCQueue(Generic[_T]):
    """A *very* small ergonomic layer on top of *multiprocessing.Queue*."""

    def __init__(self, maxsize: int = 0):
        self._queue: _mp.Queue[_T] = _mp.Queue(maxsize)

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def put(self, item: _T, timeout: float | None = None) -> None:
        """Enqueue *item* or raise :class:`TimeoutError`.

        The underlying queue may raise :class:`queue.Full` which we catch and
        re‐raise as the built‐in :class:`TimeoutError` for simplicity.
        """

        try:
            self._queue.put(item, timeout=timeout)
        except _queue.Full as exc:  # pragma: no cover – difficult to unit-test
            raise TimeoutError("Timed out while putting item into IPCQueue") from exc

    def get(self, timeout: float | None = None) -> _T:
        """Dequeue an item or raise :class:`TimeoutError`."""

        try:
            return self._queue.get(timeout=timeout)
        except _queue.Empty as exc:
            raise TimeoutError("Timed out while waiting for item from IPCQueue") from exc

    # ------------------------------------------------------------------
    # Interop helpers
    # ------------------------------------------------------------------
    @property
    def raw(self) -> _mp.Queue[_T]:
        """Return the raw *multiprocessing.Queue* instance.

        Useful when an existing process needs direct access without going
        through the wrapper layer (e.g. when passing the queue to a worker
        process spawned with *spawn*).
        """

        return self._queue

    # ------------------------------------------------------------------
    # Convenience dunders
    # ------------------------------------------------------------------
    def __iter__(self):
        while True:
            yield self.get()

    def __len__(self):
        return self._queue.qsize()

    def close(self):
        """Close the underlying queue and join the helper thread."""
        self._queue.close()
        self._queue.join_thread()

    def __del__(self):  # pragma: no cover – non-deterministic finaliser
        try:
            self.close()
        except (ValueError, OSError):
            # Already closed or never fully initialised – ignore.
            pass 