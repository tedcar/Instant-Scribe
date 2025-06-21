import importlib
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module,symbol",
    [
        ("audio", "AudioStreamer"),
        ("audio", "VADAudioGate"),
        ("core", "ConfigManager"),
        ("ui", "TrayApp"),
        ("ipc", "Message"),
    ],
)
def test_symbol_importable(module: str, symbol: str):  # noqa: D401 – test
    mod = importlib.import_module(module)
    assert hasattr(mod, symbol), f"{symbol} missing in {module} package"


def test_generate_api_docs(tmp_path, monkeypatch):  # noqa: D401 – test
    """Ensure the *scripts/generate_api_docs.py* script completes without error.

    The script writes to *docs/api/* – redirect to a temporary directory during
    the test to avoid polluting the workspace.
    """
    monkeypatch.setenv("DOCS_OUTPUT_DIR", str(tmp_path))
    subprocess.check_call([sys.executable, "scripts/generate_api_docs.py"])
    # Expect at least *index.html* for the first package.
    generated_files = list(tmp_path.rglob("*.html"))
    assert generated_files, "No HTML documentation generated"


def test_adr_present():  # noqa: D401 – test
    adr_path = Path("docs/adr/0001-modularize-codebase.md")
    assert adr_path.exists(), "ADR file for modularisation is missing"
    content = adr_path.read_text(encoding="utf-8")
    assert "Modularise Codebase" in content 