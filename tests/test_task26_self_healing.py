import inspect
import sys
from pathlib import Path
import types
import importlib
import pytest
import importlib.util as _ilu  # noqa: E402

# Ensure repository root on sys.path so importing works in CI
ROOT_DIR = Path(inspect.getfile(inspect.currentframe())).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Dynamically load the *system_check* module from its file path. Relying on
# implicit namespace packages caused issues on some CI environments.
_system_check_spec = _ilu.spec_from_file_location(
    "system_check", ROOT_DIR / "scripts" / "system_check.py"
)
sc = _ilu.module_from_spec(_system_check_spec)  # type: ignore
# dynamic loader (mypy ignored via global configuration)
assert _system_check_spec.loader is not None
_system_check_spec.loader.exec_module(sc)  # type: ignore  # pragma: no cover


class _MutableFlag(dict):
    """Simple mutable mapping for tracking side effects in monkeypatched funcs."""


def test_nvidia_driver_self_heal(monkeypatch):
    """When *nvidia-smi* is absent the checker should attempt self-healing once."""
    state = _MutableFlag(install_called=False)

    # Patch *shutil.which* so that the very first call for 'nvidia-smi' returns
    # *None* (missing) and subsequent calls pretend the binary appeared after
    # installation.
    def _fake_which(cmd):
        if cmd == "nvidia-smi":
            return None if not state["install_called"] else "/usr/bin/nvidia-smi"
        return f"/usr/bin/{cmd}"

    monkeypatch.setattr(sc.shutil, "which", _fake_which, raising=True)

    # Intercept installation attempt so no external commands are executed.
    def _fake_install(dep):
        assert dep == "NVIDIA.Display.Driver"  # Expected Winget ID
        state["install_called"] = True
        return True

    monkeypatch.setattr(sc, "_attempt_install_dependency", _fake_install, raising=True)

    # Stub out *subprocess.check_output* used for version query.
    monkeypatch.setattr(sc.subprocess, "check_output", lambda *a, **kw: "999.99\n", raising=True)

    # The function should **not** raise once self-healing succeeds.
    sc._require_nvidia_driver()


def test_command_self_heal(monkeypatch):
    """Missing auxiliary CLI tools (e.g. sox) should trigger a self-heal attempt."""
    state = _MutableFlag(install_called=False)

    def _fake_which(cmd):
        if cmd == "sox":
            return None if not state["install_called"] else "/usr/bin/sox"
        return f"/usr/bin/{cmd}"

    monkeypatch.setattr(sc.shutil, "which", _fake_which, raising=True)

    def _fake_install(dep):
        state["install_called"] = True
        assert dep == "sox"
        return True

    monkeypatch.setattr(sc, "_attempt_install_dependency", _fake_install, raising=True)

    # Fake subprocess.run used for version retrieval.
    class _FakeResult:
        stdout = "sox 14.4.2"

    monkeypatch.setattr(sc.subprocess, "run", lambda *a, **kw: _FakeResult(), raising=True)

    sc._require_command("sox", "--version")


def test_nvidia_driver_missing_raises(monkeypatch):
    """If self-healing fails the checker must raise *CheckError*."""
    monkeypatch.setattr(sc.shutil, "which", lambda cmd: None, raising=True)
    monkeypatch.setattr(sc, "_attempt_install_dependency", lambda dep: False, raising=True)

    with pytest.raises(sc.CheckError):
        sc._require_nvidia_driver() 