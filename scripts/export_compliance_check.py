#!/usr/bin/env python3.10
"""Export-control compliance check.

This lightweight tool scans ``requirements.txt`` for packages that provide
strong cryptography.  The presence of any such package may trigger export-
control obligations, so we enforce a hard ban at packaging time.

The list is intentionally conservative – feel free to extend it when new
libraries are introduced.
"""
from __future__ import annotations

import pathlib
import sys

BANNED_PACKAGES = {
    "cryptography",
    "pycrypto",
    "pycryptodome",
    "pycryptodomex",
    "m2crypto",
    "pynacl",
    "openssl",
}


def _iter_requirement_names(req_file: pathlib.Path):
    for line in req_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue
        name_part = line.split("#", 1)[0].strip()
        if "==" in name_part:
            name_part = name_part.split("==", 1)[0]
        name = name_part.split("[")[0].strip().lower()
        yield name


def main() -> None:  # pragma: no cover – thin CLI wrapper
    req_path = pathlib.Path("requirements.txt")
    if not req_path.exists():
        print("[export_compliance_check] ERROR: requirements.txt not found", file=sys.stderr)
        sys.exit(1)

    offending = sorted({name for name in _iter_requirement_names(req_path) if name in BANNED_PACKAGES})
    if offending:
        print("[export_compliance_check] FAILED – cryptography packages detected:", ", ".join(offending), file=sys.stderr)
        sys.exit(2)

    print("[export_compliance_check] OK – no banned cryptography packages present.")


if __name__ == "__main__":
    main()