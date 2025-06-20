import configparser
from pathlib import Path


def test_installer_cfg_exists_and_valid():
    cfg_path = Path('installer.cfg')
    assert cfg_path.exists(), "installer.cfg must exist at project root"

    parser = configparser.ConfigParser()
    parser.read(cfg_path, encoding='utf-8')

    # Verify required sections
    for section in ('Application', 'Python', 'Include', 'Build'):
        assert section in parser, f"Missing '{section}' section in installer.cfg"

    # Basic field sanity checks
    app_section = parser['Application']
    assert app_section.get('name') == 'Instant Scribe'
    assert app_section.get('script') == 'watchdog.pyw', "Application must launch watchdog.pyw"

    python_section = parser['Python']
    assert python_section.get('version').startswith('3.10'), "Python version should be 3.10.x"

    build_section = parser['Build']
    template = build_section.get('nsi_template')
    assert template, "nsi_template must be specified for custom post-install logic"
    assert Path(template).exists(), "Custom NSIS template file is missing"

    # Ensure autostart registration script is present
    assert Path('scripts/register_watchdog_autostart.ps1').exists(), "Autostart PowerShell script missing" 