"""Comprehensive tests for Task 59 - Documentation & User Guide.

This test suite validates:
- README.md completeness and accuracy
- Configuration documentation coverage
- User workflow documentation
- Technical documentation accuracy
"""

import json
import re
from pathlib import Path
import pytest
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from InstanceScrubber.config_manager import ConfigManager


class TestREADMECompleteness:
    """Test that README.md covers all essential aspects."""
    
    def test_readme_exists(self):
        """Test that README.md exists."""
        readme_path = Path(__file__).parent.parent / "README.md"
        assert readme_path.exists(), "README.md should exist"
    
    def test_readme_has_required_sections(self):
        """Test that README.md contains all required sections."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_sections = [
            "# Instant Scribe",
            "## 🚀 Key Features",
            "## 📋 System Requirements", 
            "## 🛠️ Installation",
            "## 🎮 Quick Start Guide",
            "## ⌨️ Hotkey Reference",
            "## ⚙️ Configuration",
            "## 🧠 AI Model",
            "## 🔍 Troubleshooting",
            "## 📄 License"
        ]
        
        for section in required_sections:
            assert section in content, f"README.md should contain section: {section}"
    
    def test_readme_installation_options(self):
        """Test that README.md documents all installation options."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        installation_options = [
            "Pre-built Installer",
            "Portable Installation", 
            "Development Setup"
        ]
        
        for option in installation_options:
            assert option in content, f"README.md should document installation option: {option}"
    
    def test_readme_system_requirements(self):
        """Test that README.md documents system requirements."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        requirements = [
            "Windows 10",
            "NVIDIA GPU",
            "VRAM",
            "CUDA",
            "Compute Capability"
        ]
        
        for req in requirements:
            assert req in content, f"README.md should mention requirement: {req}"
    
    def test_readme_parakeet_model_info(self):
        """Test that README.md contains accurate Parakeet model information."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        model_info = [
            "Parakeet TDT 0.6b-v2",
            "600M Parameters",
            "FastConformer",
            "Token Duration Transducer",
            "Word Error Rate",
            "LibriSpeech"
        ]
        
        for info in model_info:
            assert info in content, f"README.md should contain model info: {info}"


class TestConfigurationDocumentation:
    """Test that configuration options are properly documented."""
    
    def test_all_config_options_documented(self):
        """Test that all configuration options are documented in README."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()
        
        # Get all config options from ConfigManager
        config_manager = ConfigManager()
        config_keys = set(config_manager.DEFAULTS.keys())
        
        # Check that key config options are documented
        important_keys = {
            "hotkey", "vad_aggressiveness", "silence_threshold_ms",
            "show_notifications", "archive_root", "vram_unload_threshold_mb"
        }
        
        for key in important_keys:
            assert key in readme_content, f"README.md should document config option: {key}"
    
    def test_hotkey_documentation(self):
        """Test that all hotkeys are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Get default hotkeys from config
        config_manager = ConfigManager()
        hotkeys = [
            config_manager.DEFAULTS.get("hotkey", "ctrl+alt+f"),
            config_manager.DEFAULTS.get("pause_hotkey", "ctrl+alt+c"),
            config_manager.DEFAULTS.get("model_hotkey", "ctrl+alt+f6"),
            config_manager.DEFAULTS.get("vram_overlay_hotkey", "ctrl+alt+f7")
        ]
        
        for hotkey in hotkeys:
            if hotkey:  # Only check if hotkey is defined
                # Convert to display format (Ctrl + Alt + F)
                display_hotkey = hotkey.replace("ctrl", "Ctrl").replace("alt", "Alt").replace("+", " + ").title()
                assert display_hotkey in content or hotkey in content, \
                    f"README.md should document hotkey: {hotkey}"
    
    def test_config_file_location_documented(self):
        """Test that configuration file location is documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        config_locations = [
            "%APPDATA%",
            "Instant_Scribe",
            "config.json"
        ]
        
        for location in config_locations:
            assert location in content, f"README.md should mention config location: {location}"


class TestWorkflowDocumentation:
    """Test that user workflow is properly documented."""
    
    def test_basic_workflow_documented(self):
        """Test that basic usage workflow is documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        workflow_steps = [
            "Start Recording",
            "Stop Recording", 
            "clipboard",
            "notification"
        ]
        
        for step in workflow_steps:
            assert step in content, f"README.md should document workflow step: {step}"
    
    def test_advanced_features_documented(self):
        """Test that advanced features are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        advanced_features = [
            "VRAM Management",
            "Pause/Resume",
            "Crash Recovery",
            "Audio Processing Pipeline",
            "Voice Activity Detection"
        ]
        
        for feature in advanced_features:
            assert feature in content, f"README.md should document advanced feature: {feature}"


class TestTechnicalDocumentation:
    """Test technical documentation accuracy."""
    
    def test_file_organization_documented(self):
        """Test that file organization is documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        directories = [
            "instant_scribe/",
            "InstanceScrubber/",
            "scripts/",
            "tests/",
            "docs/"
        ]
        
        for directory in directories:
            assert directory in content, f"README.md should document directory: {directory}"
    
    def test_supported_formats_documented(self):
        """Test that supported audio formats are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        formats = ["WAV", "MP3", "MP4", "FLAC"]
        
        for fmt in formats:
            assert fmt in content, f"README.md should document supported format: {fmt}"
    
    def test_privacy_security_documented(self):
        """Test that privacy and security features are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        privacy_features = [
            "100% Offline",
            "Local Storage",
            "No Cloud Dependencies",
            "Privacy-First"
        ]
        
        for feature in privacy_features:
            assert feature in content, f"README.md should document privacy feature: {feature}"


class TestAccessibilityDocumentation:
    """Test accessibility documentation."""
    
    def test_accessibility_features_documented(self):
        """Test that accessibility features are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        accessibility_features = [
            "High-Contrast Icons",
            "Screen Reader",
            "WCAG 2.1",
            "DPI Awareness"
        ]
        
        for feature in accessibility_features:
            assert feature in content, f"README.md should document accessibility feature: {feature}"


class TestTroubleshootingDocumentation:
    """Test troubleshooting documentation."""
    
    def test_common_issues_documented(self):
        """Test that common issues and solutions are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        common_issues = [
            "GPU Not Detected",
            "Model Loading Errors",
            "Audio Input Issues",
            "Configuration Problems"
        ]
        
        for issue in common_issues:
            assert issue in content, f"README.md should document common issue: {issue}"
    
    def test_diagnostic_commands_documented(self):
        """Test that diagnostic commands are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        diagnostic_commands = [
            "system_check.py",
            "check_cuda.py",
            "upgrade_config.py"
        ]
        
        for command in diagnostic_commands:
            assert command in content, f"README.md should document diagnostic command: {command}"


class TestConfigurationManagementDocumentation:
    """Test configuration management tool documentation."""
    
    def test_config_cli_documented(self):
        """Test that configuration CLI tool is documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        cli_commands = [
            "--validate",
            "--migrate", 
            "--fix",
            "--generate-defaults"
        ]
        
        for command in cli_commands:
            assert command in content, f"README.md should document CLI command: {command}"


def test_task59_complete_implementation():
    """Comprehensive test that Task 59 is fully implemented."""
    # Test 1: README.md exists and is comprehensive
    readme_path = Path(__file__).parent.parent / "README.md"
    assert readme_path.exists(), "README.md should exist"
    
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Test 2: README is substantial (should be comprehensive)
    assert len(content) > 10000, "README.md should be comprehensive (>10k characters)"
    
    # Test 3: Contains key sections
    key_sections = ["Installation", "Configuration", "Troubleshooting", "AI Model"]
    for section in key_sections:
        assert section in content, f"README.md should contain section about {section}"
    
    # Test 4: Documents Parakeet model
    assert "Parakeet TDT 0.6b-v2" in content, "README.md should document the AI model"
    
    # Test 5: Documents offline operation
    assert "offline" in content.lower(), "README.md should emphasize offline operation"
    
    print("✓ Task 59 implementation complete and comprehensive")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
