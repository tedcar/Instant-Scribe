import inspect
from pathlib import Path
import multiprocessing as mp

import pytest

# Ensure repo root on sys.path so local imports resolve inside the spawned process
import sys
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ipc import IPCQueue  # noqa: E402
from ipc.messages import Transcribe, Shutdown, Response  # noqa: E402


# ---------------------------------------------------------------------------
# Helper – the simplest possible echo worker used for the integration test
# ---------------------------------------------------------------------------

def _echo_worker(request_q: mp.Queue, response_q: mp.Queue):
    """Process that echoes back audio it receives in a *Transcribe* message."""

    # Import inside the process to avoid pickling issues on Windows spawn
    from ipc.messages import Transcribe, Shutdown, Response  # pylint: disable=import-outside-toplevel

    while True:
        msg = request_q.get()
        if isinstance(msg, Transcribe):
            response_q.put(Response(result=msg.audio))
        elif isinstance(msg, Shutdown):
            break


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ipc_echo_cycle(tmp_path):
    """Dummy audio round‐trips via echo worker."""

    # GIVEN request/response queues and a background worker
    req_q = IPCQueue()
    resp_q = IPCQueue()

    worker = mp.Process(target=_echo_worker, args=(req_q.raw, resp_q.raw))
    worker.start()

    try:
        dummy_audio = b"\x00\x01\x02\x03" * 1024
        req_q.put(Transcribe(audio=dummy_audio))
        response: Response[bytes] = resp_q.get(timeout=2)

        # THEN the response payload should exactly match the input
        assert response.result == dummy_audio

    finally:
        # Always shut down the worker, even if the assertion fails, to avoid
        # orphaned processes when running the test suite.
        req_q.put(Shutdown(reason="tests complete"))
        worker.join(timeout=5) 