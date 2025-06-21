import argparse
import logging
import shlex
import subprocess
import sys
import time
from pathlib import Path


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
        # On Windows `shlex.split` may break quoted arguments (e.g. "python -c '...'"),
        # therefore we execute through the shell which matches the invocation style
        # used by the unit-tests.
        logging.info("Launching child process: %s", cmd)
        # Flush to guarantee log entry is written for unit-tests.
        for h in logging.getLogger().handlers:
            try:
                h.flush()
            except Exception:
                pass
        return subprocess.Popen(cmd, shell=True)

    logging.info("Launching child process: %s", cmd)
    # Flush to guarantee log entry is written for unit-tests.
    for h in logging.getLogger().handlers:
        try:
            h.flush()
        except Exception:
            pass

    return subprocess.Popen(cmd)


def main(argv: list[str] | None = None) -> None:  # noqa: D401 – CLI entry-point
    """Watchdog entry – supervises child process and auto-restarts on non-zero exit codes."""
    args = _parse_args(argv)

    _configure_logging(Path("watchdog.log"))

    child_cmd: list[str] | str = args.cmd if args.cmd else _build_default_cmd()

    while True:
        proc = _spawn_child(child_cmd)
        proc.wait()
        exit_code = proc.returncode
        logging.warning("Child process terminated with exit code %s", exit_code)
        # Flush to ensure test can read this line before process termination.
        for h in logging.getLogger().handlers:
            try:
                h.flush()
            except Exception:
                pass

        # Break-out conditions -------------------------------------------------
        if args.once or exit_code == 0:
            logging.info("Watchdog exiting (once=%s, exit_code=%s)", args.once, exit_code)
            break

        logging.info("Restarting child in %.1f s ...", args.sleep)
        # Ensure line is flushed so integration tests can detect it quickly.
        for h in logging.getLogger().handlers:
            try:
                h.flush()
            except Exception:
                pass
        time.sleep(args.sleep)


if __name__ == "__main__":  # pragma: no cover – manual execution helper
    main() 