import os
import json
from pathlib import Path

import pytest

# Ensure the root of the repo is on sys.path if tests run via `python -m pytest` from subdir
import sys, inspect
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from InstanceScrubber.config_manager import ConfigManager  # noqa: E402


@pytest.fixture()
def temp_appdata(monkeypatch, tmp_path):
    """Redirect %APPDATA% to a temporary directory for test isolation."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


def test_save_load_round_trip(temp_appdata):
    """Settings saved by one instance should be visible when reloaded by another."""
    # GIVEN a pristine configuration environment
    cm1 = ConfigManager(app_name="TestApp")

    # WHEN we mutate a setting and rely on the default auto-save behaviour
    cm1.set("hotkey", "ctrl+shift+h")

    # THEN a brand-new instance should observe the persisted value
    cm2 = ConfigManager(app_name="TestApp")
    assert cm2.get("hotkey") == "ctrl+shift+h"

    # AND the config file should exist on disk inside the redirected %APPDATA%
    expected_path = Path(os.environ["APPDATA"]) / "TestApp" / "config.json"
    assert expected_path.is_file()

    # FINALLY, confirm on-disk JSON actually contains the mutated value for defence-in-depth
    data = json.loads(expected_path.read_text(encoding="utf-8"))
    assert data["hotkey"] == "ctrl+shift+h" 