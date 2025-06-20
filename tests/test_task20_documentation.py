from pathlib import Path


README_PATH = Path("README.md")
TROUBLESHOOT_PATH = Path("docs/TROUBLESHOOTING.md")
DIAGRAM_PATH = Path("docs/diagram.mmd")


def test_readme_has_quick_start_and_hotkeys():
    content = README_PATH.read_text(encoding="utf-8")
    assert "Quick Start for End Users" in content, "README is missing the Quick Start section"
    assert "Hotkeys Reference" in content, "README is missing the Hotkeys Reference section"
    assert "Ctrl + Alt + F" in content, "Recording hotkey not documented"
    assert "Ctrl + Alt + F6" in content, "VRAM toggle hotkey not documented"


def test_docs_files_exist():
    assert TROUBLESHOOT_PATH.exists(), "TROUBLESHOOTING.md does not exist"
    assert DIAGRAM_PATH.exists(), "Architecture diagram is missing"


def test_mermaid_diagram_starts_with_graph():
    diagram_content = DIAGRAM_PATH.read_text(encoding="utf-8").lstrip()
    assert diagram_content.startswith("graph"), "Mermaid diagram should start with 'graph' keyword" 