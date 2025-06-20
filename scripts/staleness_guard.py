#!/usr/bin/env python3
"""Staleness Guard – CI helper for Task 17.2.

The script scans *progress/DEV_TASKS.md* for any unchecked `- [ ]` task lines
and determines the last commit timestamp for each line via `git blame`.  If a
pending task has not been modified within *MAX_AGE_DAYS* the script exits with
code 1 causing the CI job to fail.

Usage (CI):
    python scripts/staleness_guard.py --max-age 30

The script prints a table of stale tasks so maintainers can decide whether to
close, re-prioritise or update the tasks.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEV_TASKS_MD = Path("progress/DEV_TASKS.md")


def _run(cmd: List[str]) -> str:
    """Run *cmd* returning *stdout* decoded as UTF-8."""
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True)
    return result.stdout


def _parse_unchecked_tasks(lines: List[str]) -> List[Tuple[int, str]]:
    """Return list of *(lineno, text)* for unchecked task lines."""
    tasks: List[Tuple[int, str]] = []
    for idx, ln in enumerate(lines, start=1):
        if ln.lstrip().startswith("- [ ]"):
            tasks.append((idx, ln.rstrip()))
    return tasks


def _line_timestamp(path: Path, lineno: int) -> _dt.datetime:
    """Return the author time for *lineno* using `git blame`."""
    blame = _run([
        "git",
        "blame",
        f"-L{lineno},{lineno}",
        "--line-porcelain",
        str(path),
    ])
    for l in blame.splitlines():
        if l.startswith("author-time "):
            ts = int(l.split()[1])
            return _dt.datetime.utcfromtimestamp(ts)
    # Fallback – shouldn't happen but keep deterministic behaviour
    return _dt.datetime.utcnow()


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: D401 – simple CLI
    parser = argparse.ArgumentParser(description="Fail build on stale dev tasks")
    parser.add_argument("--max-age", type=int, default=30, help="Allowed age in days")
    args = parser.parse_args()

    if not DEV_TASKS_MD.exists():
        print("::warning::DEV_TASKS.md not found – skipping staleness check", file=sys.stderr)
        return

    lines = DEV_TASKS_MD.read_text(encoding="utf-8").splitlines()
    tasks = _parse_unchecked_tasks(lines)
    if not tasks:
        return  # All done 💚

    now = _dt.datetime.utcnow()
    stale: List[Tuple[int, str, int]] = []
    for lineno, text in tasks:
        age_days = (now - _line_timestamp(DEV_TASKS_MD, lineno)).days
        if age_days > args.max_age:
            stale.append((lineno, text, age_days))

    if not stale:
        return

    print("::error::The following dev tasks are stale (> %d days):" % args.max_age)
    for lineno, text, age in stale:
        print(f"L{lineno:4d} | {age:3d}d | {text}")
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        # git command failed – treat as warning not to block local runs
        print(f"::warning::git command failed: {exc}", file=sys.stderr)
        sys.exit(0)