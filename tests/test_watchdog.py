import inspect
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure repository root on sys.path so importing watchdog works in CI.
# ---------------------------------------------------------------------------
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture()
def _patch_subprocess(monkeypatch):
    """Patch *subprocess.Popen* with a deterministic stub suitable for tests.

    The first invocation exits with *returncode=1* (simulating a crash) and the
    second invocation exits with *returncode=0* (graceful shutdown).  This
    allows tests to assert that the watchdog attempts a restart exactly once.
    """

    class _DummyProcess:  # pylint: disable=too-few-public-methods
        _invocation_count = 0

        def __init__(self, *_a, **_kw):  # noqa: D401 – signature match
            type(self)._invocation_count += 1
            self._id = type(self)._invocation_count
            # First run fails, second run succeeds
            self.returncode = 1 if self._id == 1 else 0

        def wait(self):  # noqa: D401 – stub
            # No-op: child considered terminated immediately
            pass

    monkeypatch.setattr("watchdog.subprocess.Popen", _DummyProcess, raising=True)
    yield _DummyProcess


def test_watchdog_restarts_then_exits(tmp_path, monkeypatch, _patch_subprocess):
    """End‐to‐end test: watchdog restarts crashed child exactly once then exits."""

    monkeypatch.chdir(tmp_path)

    import importlib

    watchdog_mod = importlib.import_module("watchdog")

    # Run *main* in test-mode: --sleep 0 speeds up loop and --cmd dummy skipped
    watchdog_mod.main(["--sleep", "0"])

    # The patched Popen should have been invoked twice (crash + restart)
    assert _patch_subprocess._invocation_count == 2  # type: ignore[attr-defined]

    # The watchdog.log should exist in tmp directory
    assert Path("watchdog.log").is_file() 