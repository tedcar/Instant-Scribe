import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    """Helper to run a command and assert zero exit status."""
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert (
        result.returncode == 0
    ), f"Command {' '.join(cmd)} failed with exit code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_black_formatting() -> None:
    _run(["black", "--check", "tests"])


def test_isort_imports() -> None:
    _run(["isort", "--check-only", "tests"])


def test_flake8_lint() -> None:
    _run(["flake8", "tests"])


def test_mypy_type_checking() -> None:
    # Run mypy in quiet mode to reduce noise on success, limited to tests directory
    _run(["mypy", "--config-file", "mypy.ini", "tests"]) 