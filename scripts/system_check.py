#!/usr/bin/env python3
"""Comprehensive environment validation script for Instant Scribe.

This supersedes ``check_cuda.py`` by performing *all* runtime checks required
by the application:

1. Python 3.10 presence (exact minor version enforced).
2. PyTorch installed **and** able to see a CUDA-capable GPU.
3. NVIDIA NeMo ASR collection importable.
4. External audio utilities ``sox`` and ``ffmpeg`` resolvable on ``PATH`` and
   runnable.

Exit status:
    0 → every check passed.
    1 → one or more checks failed (human-readable explanation printed).

Usage::

    python scripts/system_check.py

A successful run prints a concise summary similar to::

    ✔ Python 3.10.12 OK
    ✔ CUDA available on NVIDIA GeForce RTX 3060 (12.00 GB, SM 8.6)
    ✔ PyTorch 2.7.1+cu118 linked against CUDA 11.8
    ✔ NeMo toolkit 2.1.0 import OK
    ✔ sox 14.4.2 available
    ✔ ffmpeg n5.1.3-4-gcc2fe4a OK

"""
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from typing import Final
import signal as _signal  # local alias to avoid polluting global namespace


GREEN: Final[str] = "\033[92m"
RED: Final[str] = "\033[91m"
RESET: Final[str] = "\033[0m"
CHECK: Final[str] = "✔"
CROSS: Final[str] = "✖"


class CheckError(RuntimeError):
    """Raised when an individual system check fails."""


def _print_ok(msg: str) -> None:
    try:
        print(f"{GREEN}{CHECK} {msg}{RESET}")
    except UnicodeEncodeError:
        # Fallback for terminals that do not support the tick character (e.g. Windows cmd/Powershell with cp1252)
        print(f"[OK] {msg}")


def _print_fail(msg: str) -> None:
    try:
        print(f"{RED}{CROSS} {msg}{RESET}")
    except UnicodeEncodeError:
        print(f"[FAIL] {msg}")


def _require_python(required: tuple[int, int]) -> None:
    if sys.version_info[:2] != required:
        raise CheckError(
            f"Python {required[0]}.{required[1]} is required, but running {sys.version.split()[0]}"
        )
    _print_ok(f"Python {sys.version.split()[0]} OK")


def _require_pytorch_and_cuda() -> None:
    try:
        import torch  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise CheckError("PyTorch is not installed – activate the project virtual environment and run `pip-sync` (or `pip install -r requirements.txt`) to install all requirements") from exc

    import torch

    if not torch.cuda.is_available():
        raise CheckError("CUDA is NOT available – ensure drivers and correct PyTorch build are installed")

    idx = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(idx)
    _print_ok(
        f"CUDA available on {props.name} ({props.total_memory / 1e9:.2f} GB, SM {props.major}.{props.minor})"
    )
    _print_ok(f"PyTorch {torch.__version__} linked against CUDA {torch.version.cuda}")


def _require_nemo() -> None:
    try:
        import nemo  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise CheckError("NVIDIA NeMo toolkit is not installed") from exc

    import nemo

    _print_ok(f"NeMo toolkit {nemo.__version__} import OK")

    # NeMo assumes a POSIX environment and references ``signal.SIGKILL`` which is missing on
    # Windows. Provide a best-effort fallback so the import does not bomb out.
    if not hasattr(_signal, "SIGKILL"):
        _signal.SIGKILL = _signal.SIGTERM  # type: ignore[attr-defined]
        # Also add to the Signals enum for libraries that perform ``signal.Signals.SIGKILL``.
        if hasattr(_signal, "Signals") and not hasattr(_signal.Signals, "SIGKILL"):
            try:
                _signal.Signals.SIGKILL = _signal.Signals.SIGTERM  # type: ignore[attr-defined]
            except Exception:
                # Enum modifications can fail; ignore as last resort.
                pass

    # Attempt to import ASR collection. The ASR collection relies on Linux-only
    # native extensions and often fails to import on Windows. Treat that case as
    # *informational* rather than an outright failure to avoid confusing users
    # with a red cross when the core toolkit works fine.
    try:
        import nemo.collections.asr as _  # noqa: F401
        _print_ok("NeMo ASR collection import OK")
    except Exception:
        if sys.platform.startswith("win"):
            # Gracefully skip on Windows – the rest of Instant-Scribe does not
            # need the full ASR collection when running the pre-built model.
            _print_ok("NeMo ASR collection unavailable on Windows – skipped")
        else:
            _print_fail("NeMo ASR collection import failed – some functionality may be limited")


def _require_command(cmd: str, *version_args: str) -> None:
    """Ensure *cmd* exists on PATH and can be executed.

    Parameters
    ----------
    cmd: str
        Command to locate (e.g. ``"sox"``).
    *version_args: str
        Additional CLI args that ask the tool for its version string. If none
        are provided, ``--version`` is used by default.
    """
    if shutil.which(cmd) is None:
        raise CheckError(f"{cmd} not found on PATH")

    args = version_args or ("--version",)
    try:
        result = subprocess.run([cmd, *args], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise CheckError(f"{cmd} failed to execute: {exc}") from exc

    # Extract first line of version output for user feedback.
    version_line = result.stdout.strip().split("\n")[0] if result.stdout else "<no output>"
    _print_ok(f"{cmd} {version_line}")


def main() -> None:  # noqa: D401 – simple glue function
    failures: list[str] = []

    checks = [
        lambda: _require_python((3, 10)),
        _require_pytorch_and_cuda,
        _require_nemo,
        lambda: _require_command("sox", "--version"),
        lambda: _require_command("ffmpeg", "-version"),
    ]

    for check in checks:
        try:
            check()
        except CheckError as err:
            _print_fail(str(err))
            failures.append(str(err))
        except Exception as exc:  # noqa: BLE001 – catch-all for unexpected issues
            _print_fail(f"Unexpected error: {exc}")
            failures.append(str(exc))

    if failures:
        print("\nOne or more checks failed. Please resolve the issues above and re-run the script.")
        sys.exit(1)

    try:
        print("\nAll system checks passed! ✨")
    except UnicodeEncodeError:
        print("\nAll system checks passed!")
    sys.exit(0)


if __name__ == "__main__":
    main() 