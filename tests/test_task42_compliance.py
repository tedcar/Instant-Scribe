import pathlib
import re
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(cmd):
    """Utility wrapper around subprocess.run returning CompletedProcess."""
    return subprocess.run(cmd, capture_output=True, text=True)


def test_license_notice_generation(tmp_path):
    """The NOTICE file must be generated and contain every pinned dependency."""
    notice_path = tmp_path / "NOTICE"
    result = _run([sys.executable, "scripts/license_audit.py", "--output", str(notice_path)])
    # Ensure command executed successfully
    assert result.returncode == 0, result.stderr
    assert notice_path.exists(), "NOTICE file was not created"

    notice_content = notice_path.read_text(encoding="utf-8")
    packages = {
        line.split("==", 1)[0].split("[")[0].strip()
        for line in (PROJECT_ROOT / "requirements.txt").read_text().splitlines()
        if "==" in line
    }

    # Extract names present in NOTICE (before first whitespace)
    present = {
        re.split(r"\s+", l)[0]
        for l in notice_content.splitlines()
        if "—" in l or "-" in l  # en-dash fallback for some shells
    }

    missing = packages - present
    assert not missing, f"Missing packages in NOTICE: {', '.join(sorted(missing))}"


def test_export_compliance_script():
    """export_compliance_check.py must exit with status 0 (no banned packages)."""
    result = _run([sys.executable, "scripts/export_compliance_check.py"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_installer_cfg_includes_notice():
    """installer.cfg must reference the NOTICE file in its files list."""
    cfg_text = (PROJECT_ROOT / "installer.cfg").read_text()
    assert "NOTICE" in cfg_text, "installer.cfg does not bundle NOTICE file"