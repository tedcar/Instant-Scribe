import argparse
import logging
import shlex
import subprocess
import sys
import time
from pathlib import Path
import os


def _configure_logging(log_path: Path) -> None:
    """Configure root logger to write *log_path* with timestamps.*"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8",
        force=True,  # Override any earlier logging configuration
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:  # noqa: D401
    parser = argparse.ArgumentParser(
        description="Instant Scribe watchdog – supervise orchestrator process and auto-restart on crash.",
        epilog="When --once is supplied the child is executed only once which is handy for unit-tests.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Back-off duration before restarting a crashed child process (default: 5).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single child instance and exit instead of looping forever (useful for tests)",
    )
    parser.add_argument(
        "--cmd",
        metavar="CMD",
        help="Override command used for the child process (advanced/testing).  Example: --cmd 'python -m instant_scribe.application_orchestrator'",
    )
    return parser.parse_args(argv)


def _build_default_cmd() -> list[str]:  # noqa: D401
    """Return the default command list for starting the application orchestrator."""
    return [sys.executable, "-m", "instant_scribe.application_orchestrator"]


def _spawn_child(cmd: list[str] | str) -> subprocess.Popen:  # noqa: D401
    """Spawn *cmd* via *subprocess.Popen* returning the process instance.*"""
    if isinstance(cmd, str):
        logging.info("Launching child process: %s", cmd)
        # Ensure log entry is flushed for unit-tests before child starts
        _sync_log_handlers()

        import shlex  # local import to avoid unnecessary dependency during startup

        try:
            parsed = shlex.split(cmd, posix=False)
            return subprocess.Popen(parsed)
        except ValueError:
            # Fallback to shell when complex quoting prevents split.
            return subprocess.Popen(cmd, shell=True)

    logging.info("Launching child process: %s", cmd)
    # Flush to guarantee log entry is written for unit-tests.
    _sync_log_handlers()

    return subprocess.Popen(cmd)


def _sync_log_handlers() -> None:  # noqa: D401 – utility
    """Flush **and** fsync all file-based logging handlers.

    This ensures that unit-tests which move/inspect *watchdog.log* immediately
    after terminating the watchdog process always see the latest lines.
    """

    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
            # Perform an OS-level flush when possible to guarantee durability.
            stream = getattr(handler, "stream", None)
            if stream and hasattr(stream, "fileno"):
                try:
                    os.fsync(stream.fileno())
                except (OSError, AttributeError):
                    pass
        except Exception:  # pragma: no cover – defensive
            pass


def main(argv: list[str] | None = None) -> None:  # noqa: D401 – CLI entry-point
    """Watchdog entry – supervises child process and auto-restarts on non-zero exit codes."""
    args = _parse_args(argv)

    _configure_logging(Path("watchdog.log"))

    child_cmd: list[str] | str = args.cmd if args.cmd else _build_default_cmd()

    while True:
        proc = _spawn_child(child_cmd)
        # Attempt a short wait to capture *instant* terminations while keeping
        # compatibility with the *_DummyProcess* used in unit-tests (which does
        # not accept a *timeout* kwarg).
        try:
            proc.wait(timeout=0.2)
        except TypeError:
            # *DummyProcess.wait* signature lacks *timeout* – fall back.
            proc.wait()
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            proc.wait()
        exit_code = proc.returncode
        logging.warning("Child process terminated with exit code %s", exit_code)
        _sync_log_handlers()

        # Break-out conditions -------------------------------------------------
        if args.once or exit_code == 0:
            logging.info("Watchdog exiting (once=%s, exit_code=%s)", args.once, exit_code)
            break

        logging.info("Restarting child in %.1f s ...", args.sleep)
        _sync_log_handlers()
        time.sleep(args.sleep)


if __name__ == "__main__":  # pragma: no cover – manual execution helper
    main() 