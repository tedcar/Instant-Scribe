import os
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path when running via `python -m pytest` from subdir
import inspect
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.resource_manager import resource_path, _determine_base_path  # noqa: E402


@pytest.fixture()
def temporary_dir(tmp_path):
    """Return the temporary directory provided by pytest as *Path*."""
    return tmp_path


def test_dev_mode_path_resolution():
    """When *not* frozen, ``resource_path`` should resolve inside repo root."""
    # GIVEN we are in development mode (no special flags set)
    assert not getattr(sys, "frozen", False), "Test assumes interpreter is not frozen!"

    base = _determine_base_path()
    # THEN base path should be the repository root directory
    assert (base / "InstanceScrubber").is_dir(), "Expected package folder under repo root"

    # AND resource_path("") should return the same base path
    assert resource_path("") == base


def test_frozen_mode_path_resolution(monkeypatch, temporary_dir):
    """In frozen mode, helper should use *sys._MEIPASS* to build paths."""
    # GIVEN a simulated PyInstaller environment
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(temporary_dir), raising=False)

    # WHEN we ask for a resource path
    dummy_rel_path = "dummy.txt"
    dummy_abs_path = Path(temporary_dir) / dummy_rel_path
    # Create a dummy file to make the path exist
    dummy_abs_path.write_text("dummy", encoding="utf-8")

    resolved_path = resource_path(dummy_rel_path)

    # THEN the resolved path should match the file inside _MEIPASS
    assert resolved_path == dummy_abs_path.resolve()
    assert resolved_path.read_text(encoding="utf-8") == "dummy"

    # Clean-up monkeypatch automatically done by fixture 