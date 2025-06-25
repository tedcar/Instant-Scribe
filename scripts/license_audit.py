#!/usr/bin/env python3.10
"""Generate NOTICE file listing third-party dependencies and their licenses.

This script reads the pinned dependency list from ``requirements.txt`` and
collects the license information available in each installed distribution's
package metadata.  The output is written to a ``NOTICE`` file which is later
bundled into the application installer.

The goal of the generated file is to comply with open-source license
requirements by providing attribution and SPDX identifiers for every bundled
third-party component.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import pathlib
import re
from typing import List, Tuple

# Mapping of common license strings to SPDX identifiers (extend as required)
_SPDX_LICENSE_MAP = {
    "MIT": "MIT",
    "BSD": "BSD-2-Clause",
    "BSD License": "BSD-2-Clause",
    "Apache 2.0": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Apache-2.0": "Apache-2.0",
    "GPLv3": "GPL-3.0-only",
    "LGPLv3": "LGPL-3.0-only",
    "MPL 2.0": "MPL-2.0",
}

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
DEFAULT_NOTICE = PROJECT_ROOT / "NOTICE"


def _extract_spdx(raw_license: str | None) -> str:
    """Return an SPDX identifier (or the raw string/``UNKNOWN``) for *raw_license*."""
    if not raw_license:
        return "UNKNOWN"

    # Try direct mapping first
    for key, spdx in _SPDX_LICENSE_MAP.items():
        if key.lower() in raw_license.lower():
            return spdx

    # Fallback: parse classifiers such as "License :: OSI Approved :: MIT License"
    match = re.search(r"License :: .*:: ([A-Za-z0-9 .+\-]+)", raw_license)
    if match:
        candidate = match.group(1).strip()
        return _SPDX_LICENSE_MAP.get(candidate, candidate)

    return raw_license.strip()


def _iter_requirements(req_path: pathlib.Path) -> Tuple[str, str]:
    """Yield ``(name, version)`` tuples parsed from *req_path*."""
    for line in req_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue

        # Discard inline comments (e.g. "foo==1.2  # via bar")
        line = line.split("#", 1)[0].strip()

        # Ignore editable installs / direct URLs – not applicable in our packaged app
        if line.startswith("-e ") or "@" in line:
            continue

        if "==" in line:
            name, version = line.split("==", 1)
        else:
            # Unpinned package (should not occur given pip-compile) – handle gracefully
            name, version = line, ""
        name = name.split("[")[0]  # Remove extras (e.g. "pkg[foo]==1.0")
        yield name.strip(), version.strip()


def audit(requirements: pathlib.Path = DEFAULT_REQUIREMENTS) -> List[Tuple[str, str, str]]:
    """Return a list ``[(name, version, spdx), ...]`` for every requirement."""
    results: List[Tuple[str, str, str]] = []

    for pkg_name, version in _iter_requirements(requirements):
        try:
            meta = metadata.metadata(pkg_name)
            raw_license: str | None = meta.get("License")
            if not raw_license:
                # Attempt to extract from classifiers when "License" metadata missing
                classifiers = meta.get_all("Classifier") or []
                for c in classifiers:
                    if c.startswith("License ::"):
                        raw_license = c
                        break
        except metadata.PackageNotFoundError:
            raw_license = None  # Package not installed in current interpreter

        spdx = _extract_spdx(raw_license)
        results.append((pkg_name, version, spdx))

    return results


def write_notice(records: List[Tuple[str, str, str]], destination: pathlib.Path = DEFAULT_NOTICE) -> None:
    """Write *records* to *destination* in a human-readable NOTICE format."""
    with destination.open("w", encoding="utf-8") as fh:
        fh.write("Instant Scribe – Third-Party Licenses\n")
        fh.write("====================================\n\n")
        fh.write("This file lists the open-source components bundled with Instant Scribe "
                 "and the SPDX identifiers of their respective licences.  "
                 "Generated automatically by scripts/license_audit.py.\n\n")

        width = max(len(name) for name, _, _ in records) + 2
        for name, version, spdx in sorted(records):
            version_part = version if version else "(unversioned)"
            fh.write(f"{name.ljust(width)}{version_part:<12} — {spdx}\n")


def _main() -> None:
    parser = argparse.ArgumentParser(description="Generate a NOTICE file with third-party licenses.")
    parser.add_argument("--requirements", type=pathlib.Path, default=DEFAULT_REQUIREMENTS,
                        help="Path to requirements.txt produced by pip-compile (default: %(default)s)")
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_NOTICE,
                        help="Destination NOTICE file path (default: %(default)s)")
    args = parser.parse_args()

    records = audit(args.requirements)
    write_notice(records, args.output)
    print(f"[license_audit] NOTICE generated at {args.output}")


if __name__ == "__main__":
    _main()