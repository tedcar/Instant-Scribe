import ast
import argparse
import pathlib
import sys
from typing import List, Set

# ---------------------------------------------------------------------------
# Configuration – forbidden modules symbol names we consider outbound network
# ---------------------------------------------------------------------------

_FORBIDDEN_PREFIXES: Set[str] = {
    "socket",
    "requests",
    "http.client",  # from http import client – capture dotted form
}


class _ImportVisitor(ast.NodeVisitor):
    """Collect *fully-qualified* import names found in a module AST."""

    def __init__(self) -> None:
        self.matches: List[str] = []

    # pylint: disable=invalid-name
    def visit_Import(self, node: ast.Import) -> None:  # noqa: D401 – AST API
        for alias in node.names:
            self._maybe_record(alias.name)

    # pylint: disable=invalid-name
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: D401 – AST API
        if node.module is None:  # e.g. `from . import foo` – ignore
            return
        module_name = node.module
        self._maybe_record(module_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_record(self, module_name: str) -> None:
        """Append *module_name* when it matches a forbidden prefix."""
        for forbidden in _FORBIDDEN_PREFIXES:
            if module_name == forbidden or module_name.startswith(f"{forbidden}."):
                self.matches.append(module_name)
                break


def _scan_file(path: pathlib.Path) -> List[str]:
    """Return a list of forbidden imports detected in *path* using ast.walk."""
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    matches: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in _FORBIDDEN_PREFIXES:
                    if alias.name == forbidden or alias.name.startswith(f"{forbidden}."):
                        matches.append(alias.name)
                        break
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            module_name = node.module
            for forbidden in _FORBIDDEN_PREFIXES:
                if module_name == forbidden or module_name.startswith(f"{forbidden}."):
                    matches.append(module_name)
                    break
    return matches


def _iter_python_files(root_dir: pathlib.Path) -> List[pathlib.Path]:
    """Yield *.py* files under *root_dir* excluding irrelevant folders."""
    SKIP_KEYWORDS = {"tests", ".venv", "site-packages", "dist-packages", "__pycache__"}
    return [
        p
        for p in root_dir.rglob("*.py")
        if not any(skip in p.parts for skip in SKIP_KEYWORDS)
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:  # noqa: D401
    parser = argparse.ArgumentParser(
        description=(
            "Static privacy audit – detect direct imports of network-capable "
            "Python standard-library or third-party modules (socket, requests, "
            "http.client)."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to scan (defaults to repository root).",
    )
    parser.add_argument(
        "--fail-on-detected",
        action="store_true",
        help="Exit with non-zero status when forbidden imports are detected.",
    )
    return parser.parse_args()


def main() -> None:  # noqa: D401 – CLI entry-point
    args = _parse_args()
    root = pathlib.Path(args.path).resolve()
    if not root.is_dir():
        print(f"ERROR: Provided path '{root}' is not a directory", file=sys.stderr)
        sys.exit(2)

    all_matches: List[str] = []
    offending_files: List[pathlib.Path] = []

    for py_file in _iter_python_files(root):
        matches = _scan_file(py_file)
        if matches:
            offending_files.append(py_file)
            all_matches.extend(f"{py_file}:{mod}" for mod in matches)

    if offending_files:
        print("Forbidden network imports detected:\n", file=sys.stderr)
        for match in all_matches:
            print(f"  - {match}", file=sys.stderr)
    else:
        print("Privacy audit passed – no forbidden network imports found.")

    if args.fail_on_detected and offending_files:
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover – import-time side-effect
    main() 