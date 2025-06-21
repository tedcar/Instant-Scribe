import inspect
import sys
from pathlib import Path

import pytest

# Ensure repo root on sys.path for import resolution
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ---------------------------------------------------------------------------
# Re-use the *pyperclip* stub installed by *test_clipboard_manager* to avoid
# clobbering the module object and breaking shared state.  If the module is
# not yet present (tests run individually), fall back to the same stub logic.
# ---------------------------------------------------------------------------

if "pyperclip" not in sys.modules:
    import types

    _clipboard_store: dict[str, str] = {}

    class _FakePyperclipModule(types.ModuleType):  # pylint: disable=too-few-public-methods
        class PyperclipException(RuntimeError):
            """Dummy exception mirroring the real one for duck-typing."""

        def copy(self, text: str):  # noqa: D401 – simple stub
            _clipboard_store["data"] = text

        def paste(self) -> str:  # noqa: D401 – simple stub
            return _clipboard_store.get("data", "")

    sys.modules["pyperclip"] = _FakePyperclipModule("pyperclip")

# Import shared clipboard store from existing stub
_clipboard_store = sys.modules["pyperclip"].__dict__.setdefault("_store", {})

from InstanceScrubber.clipboard_manager import copy_with_verification  # noqa: E402

_pyperclip = sys.modules["pyperclip"]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_clipboard():
    try:
        _pyperclip.copy("")
    except Exception:
        pass


@pytest.fixture()
def tmp_output_dir(tmp_path):
    return tmp_path

# ---------------------------------------------------------------------------
# Task-36 specific tests
# ---------------------------------------------------------------------------

def test_crc32_mismatch_triggers_fallback(monkeypatch, tmp_output_dir):
    """When the pasted data is corrupted, fallback file should be written."""

    original_text = "Integrity check sample"

    # Normal copy stores text as-is … but we will corrupt *paste*.
    orig_paste = _pyperclip.paste

    def corrupt_paste():  # noqa: D401 – stub
        stored = orig_paste()
        # Remove last char to change CRC32 while still being plausible text.
        return stored[:-1]

    monkeypatch.setattr(sys.modules["pyperclip"], "paste", corrupt_paste)

    success = copy_with_verification(original_text, max_retries=1, fallback_dir=tmp_output_dir)
    assert success is False  # Should signal fallback path

    # A single *.txt* fallback file must exist containing the original text
    files = list(tmp_output_dir.iterdir())
    assert len(files) == 1 and files[0].suffix == ".txt"
    assert files[0].read_text(encoding="utf-8").startswith(original_text) 