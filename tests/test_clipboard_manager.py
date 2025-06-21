import inspect
import sys
from pathlib import Path
import types

import pytest

# Safely obtain the current frame for static analysers – *currentframe()* can
# return *None* so we assert non-null before use.  The assert is runtime-cheap
# and satisfies **mypy/ruff** Optional-to-str narrowing (Task 36 linter fix).
_frame = inspect.currentframe()
assert _frame is not None, "inspect.currentframe() returned None unexpectedly"

ROOT_DIR = Path(inspect.getfile(_frame)).resolve().parents[1]  # type: ignore[arg-type]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ---------------------------------------------------------------------------
# Stub out *pyperclip* so we can fully control behaviour on CI runners that
# may not provide a functional clipboard (e.g. headless Linux).
# ---------------------------------------------------------------------------

_clipboard_store: dict[str, str] = {}

class _FakePyperclipModule(types.ModuleType):  # pylint: disable=too-few-public-methods
    class PyperclipException(RuntimeError):
        """Dummy exception mirroring the real one for duck-typing."""

    def copy(self, text: str):  # noqa: D401 – simple stub
        _clipboard_store["data"] = text

    def paste(self) -> str:  # noqa: D401 – simple stub
        return _clipboard_store.get("data", "")

# Inject stub before importing SUT
sys.modules["pyperclip"] = _FakePyperclipModule("pyperclip")

from InstanceScrubber.clipboard_manager import copy_with_verification  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_clipboard():
    _clipboard_store.clear()


@pytest.fixture()
def tmp_output_dir(tmp_path):
    """Return a temporary directory path usable by tests as *fallback_dir*."""
    return tmp_path

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_copy_success():
    """A normal happy-path call should copy and verify exactly once."""
    test_payload = "Hello world"

    assert copy_with_verification(test_payload)
    assert _clipboard_store["data"] == test_payload


def test_retry_then_success(monkeypatch):
    """First attempt fails, second succeeds – function returns True."""

    call_count = {"copy": 0}

    def flakey_copy(text):  # noqa: D401 – stub
        call_count["copy"] += 1
        if call_count["copy"] == 1:
            raise _FakePyperclipModule.PyperclipException("busy")
        _clipboard_store["data"] = text

    monkeypatch.setattr(sys.modules["pyperclip"], "copy", flakey_copy)

    assert copy_with_verification("retry text", max_retries=2, retry_delay=0)
    assert call_count["copy"] == 2


def test_fallback_file_written(tmp_output_dir, monkeypatch):
    """If all retries fail, a *.txt* file should be created instead."""

    # Always raise to force fallback
    monkeypatch.setattr(
        sys.modules["pyperclip"],
        "copy",
        lambda _txt: (_ for _ in ()).throw(_FakePyperclipModule.PyperclipException("denied")),
    )

    created = copy_with_verification("some sample text for fallback", max_retries=1, fallback_dir=tmp_output_dir)
    assert created is False  # Indicates fallback path

    # One file should exist in *tmp_output_dir*
    files = list(tmp_output_dir.iterdir())
    assert len(files) == 1 and files[0].suffix == ".txt"
    assert files[0].read_text(encoding="utf-8").startswith("some sample text")


def test_large_payload_no_crash(monkeypatch):
    """Extremely large payloads should not crash the function."""

    # Prepare fake *copy* that just stores the length to avoid RAM explosion.
    def copy_len(text):  # noqa: D401 – stub
        _clipboard_store["data"] = f"len:{len(text)}"

    def paste_len():  # noqa: D401 – stub
        return "dummy"  # mismatch forces fallback

    monkeypatch.setattr(sys.modules["pyperclip"], "copy", copy_len)
    monkeypatch.setattr(sys.modules["pyperclip"], "paste", paste_len)

    huge_length = 1_000_000_000  # 1 billion chars – do *not* allocate the full string
    class _LazyHugeStr(str):  # noqa: D401 – custom lazy str
        def __new__(cls):  # noqa: D401 – simple stub
            return str.__new__(cls, "a" * 10)  # tiny placeholder
        def __len__(self):  # noqa: D401 – correct length reporting
            return huge_length

    large_payload = _LazyHugeStr()

    # Should execute without raising MemoryError or similar.
    copy_with_verification(large_payload, max_retries=1)


def test_crc_mismatch_triggers_fallback(tmp_output_dir, monkeypatch):
    """If CRC32 does not match, fallback file should be created (Task 36)."""

    # Copy succeeds but paste returns modified data causing checksum mismatch.
    monkeypatch.setattr(sys.modules["pyperclip"], "paste", lambda: "tampered text")

    result = copy_with_verification("original text", max_retries=1, retry_delay=0, fallback_dir=tmp_output_dir)
    # Expect False since fallback path executed.
    assert result is False

    files = list(tmp_output_dir.iterdir())
    assert files and files[0].suffix == ".txt"
    assert files[0].read_text(encoding="utf-8").startswith("original text") 