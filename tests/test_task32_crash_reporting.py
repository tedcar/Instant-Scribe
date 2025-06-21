import os
import sys
import time
import subprocess
import zipfile
from pathlib import Path

import pytest

import instant_scribe.crash_reporter as crash_reporter


@pytest.fixture(autouse=True)
def _cleanup_crash_logs(tmp_path, monkeypatch):  # noqa: D401 – auto‐cleanup
    """Redirect crash log & reports to *tmp_path* to keep repo clean."""
    crash_dir = tmp_path / "logs"
    reports_dir = tmp_path / "reports"

    monkeypatch.setenv("INSTANT_SCRIBE_CRASH_LOG", str(crash_dir / "crash.log"))
    monkeypatch.setenv("APPDATA", str(tmp_path))  # Windows path used by reporter

    # Reload module so env vars take effect
    import importlib

    importlib.reload(crash_reporter)

    yield

    # Explicit cleanup – no assertion errors should leave files behind
    crash_reporter.close()
    if crash_dir.exists():
        for p in crash_dir.rglob("*"):
            p.unlink(missing_ok=True)
    if reports_dir.exists():
        for p in reports_dir.rglob("*"):
            p.unlink(missing_ok=True)


def test_uncaught_exception_creates_rotating_log(tmp_path, monkeypatch):  # noqa: D401
    log_path = tmp_path / "logs" / "crash.log"

    # Ensure path starts fresh but avoid unlinking on Windows if locked
    if log_path.exists():
        crash_reporter.close()
        try:
            log_path.unlink()
        except PermissionError:
            # File locked – allow test to proceed
            pass

    # Trigger unhandled exception via the installed excepthook
    try:
        1 / 0
    except ZeroDivisionError as exc:  # noqa: B017 – intentional
        sys.excepthook(type(exc), exc, exc.__traceback__)

    # Verify crash.log created and contains traceback
    assert log_path.exists(), "crash.log should be created by crash reporter"
    contents = log_path.read_text(encoding="utf-8")
    assert "ZeroDivisionError" in contents


def test_generate_report_zip_contains_log(tmp_path):  # noqa: D401
    zip_path = crash_reporter.generate_report_zip()
    assert zip_path.exists(), "Report ZIP not generated"

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "crash.log" in names, "crash.log missing in report ZIP"


def test_watchdog_restarts_crashed_process(tmp_path):  # noqa: D401 – integration
    """Spawn watchdog with failing child and verify *restart* message written."""
    log_path = tmp_path / "watchdog.log"

    # Build watchdog command: child exits immediately with code 1
    child_cmd = f'{sys.executable} -c "import sys; sys.exit(1)"'
    cmd = [
        sys.executable,
        "watchdog.py",
        "--sleep",
        "0.1",
        "--cmd",
        child_cmd,
    ]

    proc = subprocess.Popen(cmd, cwd=Path.cwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Allow enough time for at least one restart
    time.sleep(0.5)
    # Extra buffer to ensure watchdog has time to restart child
    time.sleep(0.6)

    # Terminate watchdog to end test
    proc.terminate()
    proc.wait(timeout=5)

    # Watchdog writes to *watchdog.log* in CWD. Move to tmp if exists.
    default_log = Path("watchdog.log")
    if default_log.exists():
        default_log.replace(log_path)

    assert log_path.exists(), "watchdog.log should have been created"

    text = log_path.read_text(encoding="utf-8")
    assert (
        "Restarting child" in text or "Child process terminated" in text
    ), "Watchdog did not restart the child process" 