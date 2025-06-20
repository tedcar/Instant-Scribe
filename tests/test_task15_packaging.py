import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow  # building with PyInstaller is time-consuming


@pytest.fixture(scope="session")
def pyinstaller_path():
    """Return the *pyinstaller* CLI ensuring the dependency is available."""
    try:
        import PyInstaller  # noqa: F401 – import check only
    except ImportError:  # pragma: no cover – installed on-demand in CI
        pytest.skip("PyInstaller not installed in the test environment")
    return shutil.which("pyinstaller") or "pyinstaller"


def _build_bundle(tmp_path: Path, pyinstaller_cmd: str):  # noqa: D401
    """Run PyInstaller with the project spec inside *tmp_path* build dirs."""
    spec_file = Path(__file__).parent.parent / "InstantScribe.spec"

    dist_dir = tmp_path / "dist"
    build_dir = tmp_path / "build"

    cmd = [
        pyinstaller_cmd,
        "--noconfirm",
        "--clean",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        str(spec_file),
    ]
    # Execute
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"PyInstaller failed: {result.stderr}"  # noqa: S101 – test assertion
    return dist_dir


def test_spec_builds_executable(tmp_path, pyinstaller_path):  # noqa: D401
    """End-to-end check that *InstantScribe.spec* produces an executable."""
    dist_dir = _build_bundle(tmp_path, pyinstaller_path)

    bundle_root = dist_dir / "Instant Scribe"
    # PyInstaller produces *onefile* when the spec omits a COLLECT step – in
    # that scenario the executable is located directly under *dist_dir*.
    if bundle_root.is_dir():
        search_root = bundle_root
    else:
        search_root = dist_dir

    exe_name = "Instant Scribe.exe" if sys.platform.startswith("win") else "Instant Scribe"
    executable = search_root / exe_name
    assert executable.exists(), "Frozen executable not found after PyInstaller build"  # noqa: S101 