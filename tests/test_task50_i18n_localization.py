"""Tests for Task 50: Internationalisation & Localisation Framework

Tests both string externalization (50.1) and runtime language switching (50.2).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from InstanceScrubber.i18n_manager import I18nManager, get_text, _, set_locale, get_available_locales
from InstanceScrubber.config_manager import ConfigManager


class TestI18nManager:
    """Test the core i18n manager functionality."""

    @pytest.fixture
    def temp_locale_dir(self, tmp_path):
        """Create temporary locale directory with test files."""
        locale_dir = tmp_path / "locale"
        locale_dir.mkdir()
        
        # Create English locale
        en_data = {
            "app_name": "Test App",
            "notifications": {
                "test_message": "Hello World"
            },
            "nested": {
                "deep": {
                    "value": "Deep Value"
                }
            }
        }
        (locale_dir / "en_US.json").write_text(json.dumps(en_data))
        
        # Create Spanish locale
        es_data = {
            "app_name": "Aplicación de Prueba",
            "notifications": {
                "test_message": "Hola Mundo"
            },
            "nested": {
                "deep": {
                    "value": "Valor Profundo"
                }
            }
        }
        (locale_dir / "es_ES.json").write_text(json.dumps(es_data))
        
        return locale_dir

    def test_i18n_manager_initialization(self, temp_locale_dir):
        """Test i18n manager initialization."""
        manager = I18nManager(locale_dir=temp_locale_dir)
        assert manager.current_locale == "en_US"
        assert manager.default_locale == "en_US"
        assert manager.locale_dir == temp_locale_dir

    def test_get_text_basic(self, temp_locale_dir):
        """Test basic text retrieval."""
        manager = I18nManager(locale_dir=temp_locale_dir)
        
        assert manager.get_text("app_name") == "Test App"
        assert manager.get_text("notifications.test_message") == "Hello World"
        assert manager.get_text("nested.deep.value") == "Deep Value"

    def test_get_text_missing_key(self, temp_locale_dir):
        """Test behavior with missing keys."""
        manager = I18nManager(locale_dir=temp_locale_dir)
        
        # Should return the key itself if not found
        assert manager.get_text("missing.key") == "missing.key"

    def test_set_locale(self, temp_locale_dir):
        """Test locale switching."""
        manager = I18nManager(locale_dir=temp_locale_dir)
        
        # Switch to Spanish
        result = manager.set_locale("es_ES")
        assert result is True
        assert manager.current_locale == "es_ES"
        
        # Text should now be in Spanish
        assert manager.get_text("app_name") == "Aplicación de Prueba"
        assert manager.get_text("notifications.test_message") == "Hola Mundo"

    def test_set_invalid_locale(self, temp_locale_dir):
        """Test setting an invalid locale."""
        manager = I18nManager(locale_dir=temp_locale_dir)
        
        result = manager.set_locale("invalid_LOCALE")
        assert result is False
        assert manager.current_locale == "en_US"  # Should remain unchanged

    def test_fallback_to_default_locale(self, temp_locale_dir):
        """Test fallback to default locale for missing translations."""
        # Create incomplete Spanish locale
        incomplete_es = {"app_name": "Aplicación de Prueba"}
        (temp_locale_dir / "es_ES.json").write_text(json.dumps(incomplete_es))
        
        manager = I18nManager(locale_dir=temp_locale_dir)
        manager.set_locale("es_ES")
        
        # Should get Spanish for available key
        assert manager.get_text("app_name") == "Aplicación de Prueba"
        
        # Should fallback to English for missing key
        assert manager.get_text("notifications.test_message") == "Hello World"

    def test_string_interpolation(self, temp_locale_dir):
        """Test string interpolation with variables."""
        # Add template string to locale
        en_data = json.loads((temp_locale_dir / "en_US.json").read_text())
        en_data["template"] = "Hello {name}, you have {count} messages"
        (temp_locale_dir / "en_US.json").write_text(json.dumps(en_data))
        
        manager = I18nManager(locale_dir=temp_locale_dir)
        
        result = manager.get_text("template", name="Alice", count=5)
        assert result == "Hello Alice, you have 5 messages"

    def test_get_available_locales(self, temp_locale_dir):
        """Test getting available locales."""
        manager = I18nManager(locale_dir=temp_locale_dir)
        
        locales = manager.get_available_locales()
        assert "en_US" in locales
        assert "es_ES" in locales
        assert len(locales) == 2

    def test_global_functions(self, temp_locale_dir):
        """Test global convenience functions."""
        # Mock the global manager
        with patch('InstanceScrubber.i18n_manager._global_i18n_manager') as mock_manager:
            mock_instance = MagicMock()
            mock_manager = mock_instance
            mock_instance.get_text.return_value = "Mocked Text"
            mock_instance.set_locale.return_value = True
            mock_instance.get_available_locales.return_value = ["en_US", "es_ES"]
            
            # Test global functions
            with patch('InstanceScrubber.i18n_manager.get_i18n_manager', return_value=mock_instance):
                assert get_text("test.key") == "Mocked Text"
                assert _("test.key") == "Mocked Text"
                assert set_locale("es_ES") is True
                assert get_available_locales() == ["en_US", "es_ES"]


class TestConfigManagerI18nIntegration:
    """Test integration between ConfigManager and i18n system."""

    def test_config_manager_set_locale(self):
        """Test ConfigManager.set_locale method."""
        config = ConfigManager()
        
        # Mock the i18n system
        with patch('InstanceScrubber.config_manager.set_locale') as mock_set_locale:
            mock_set_locale.return_value = True
            
            result = config.set_locale("es_ES")
            assert result is True
            assert config.get("locale") == "es_ES"
            mock_set_locale.assert_called_once_with("es_ES")

    def test_config_manager_set_locale_failure(self):
        """Test ConfigManager.set_locale with invalid locale."""
        config = ConfigManager()
        
        # Mock the i18n system to return False
        with patch('InstanceScrubber.config_manager.set_locale') as mock_set_locale:
            mock_set_locale.return_value = False
            
            result = config.set_locale("invalid_LOCALE")
            assert result is False
            # Config should not be updated if locale setting failed
            assert config.get("locale") == "en_US"  # Default value

    def test_config_manager_set_locale_no_i18n(self):
        """Test ConfigManager.set_locale when i18n system is not available."""
        config = ConfigManager()
        
        # Mock ImportError to simulate missing i18n system
        with patch('InstanceScrubber.config_manager.set_locale', side_effect=ImportError):
            result = config.set_locale("es_ES")
            assert result is True  # Should still succeed
            assert config.get("locale") == "es_ES"


class TestNotificationManagerI18n:
    """Test that NotificationManager uses localized strings."""

    def test_notification_manager_localized_app_name(self):
        """Test that NotificationManager uses localized app name."""
        with patch('InstanceScrubber.notification_manager._') as mock_gettext:
            mock_gettext.return_value = "Localized App Name"
            
            from InstanceScrubber.notification_manager import NotificationManager
            
            manager = NotificationManager()
            assert manager._app_name == "Localized App Name"
            mock_gettext.assert_called_with("app_name")

    def test_notification_manager_localized_title(self):
        """Test that NotificationManager uses localized default title."""
        with patch('InstanceScrubber.notification_manager._') as mock_gettext:
            mock_gettext.return_value = "Localized Title"
            
            from InstanceScrubber.notification_manager import NotificationManager
            
            manager = NotificationManager()
            assert manager._DEFAULT_TITLE == "Localized Title"
            mock_gettext.assert_called_with("notifications.transcription_complete")


class TestTrayAppI18n:
    """Test that TrayApp uses localized strings."""

    def test_tray_app_localized_strings(self):
        """Test that TrayApp uses localized strings for menu items."""
        with patch('InstanceScrubber.tray_app._') as mock_gettext:
            # Mock different return values for different keys
            def mock_gettext_side_effect(key):
                translations = {
                    "app_name": "Localized App",
                    "app_title": "Localized Title",
                    "tray_menu.status_listening": "Estado: Escuchando",
                    "tray_menu.status_idle": "Estado: Inactivo",
                    "tray_menu.stop_listening": "Detener Escucha",
                    "tray_menu.start_listening": "Iniciar Escucha",
                    "tray_menu.exit": "Salir",
                    "placeholders.icon_text": "IS"
                }
                return translations.get(key, key)
            
            mock_gettext.side_effect = mock_gettext_side_effect
            
            # Mock pystray to avoid GUI dependencies
            with patch('InstanceScrubber.tray_app.pystray') as mock_pystray:
                mock_icon_class = MagicMock()
                mock_pystray.Icon = mock_icon_class
                mock_pystray.Menu = MagicMock()
                mock_pystray.MenuItem = MagicMock()
                
                from InstanceScrubber.tray_app import TrayApp
                from InstanceScrubber.config_manager import ConfigManager
                
                config = ConfigManager()
                app = TrayApp(config, lambda: None, lambda: None)
                
                # Test that start() uses localized strings
                with patch.object(app, '_load_or_generate_icon'), \
                     patch.object(app, '_build_menu') as mock_build_menu:
                    
                    mock_build_menu.return_value = MagicMock()
                    app.start()
                    
                    # Verify Icon was created with localized strings
                    mock_icon_class.assert_called_once()
                    call_kwargs = mock_icon_class.call_args[1]
                    assert call_kwargs['name'] == "Localized App"
                    assert call_kwargs['title'] == "Localized Title"


def test_task50_integration():
    """Integration test for Task 50: Complete i18n workflow."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create test locale files
        locale_dir = tmp_path / "locale"
        locale_dir.mkdir()
        
        en_data = {
            "app_name": "Instant Scribe",
            "notifications": {"transcription_complete": "Transcription complete"},
            "tray_menu": {"exit": "Exit"}
        }
        (locale_dir / "en_US.json").write_text(json.dumps(en_data))
        
        es_data = {
            "app_name": "Instant Scribe",
            "notifications": {"transcription_complete": "Transcripción completada"},
            "tray_menu": {"exit": "Salir"}
        }
        (locale_dir / "es_ES.json").write_text(json.dumps(es_data))
        
        # Test the complete workflow
        manager = I18nManager(locale_dir=locale_dir)
        
        # 1. Default English
        assert manager.get_text("notifications.transcription_complete") == "Transcription complete"
        assert manager.get_text("tray_menu.exit") == "Exit"
        
        # 2. Switch to Spanish
        assert manager.set_locale("es_ES") is True
        assert manager.get_text("notifications.transcription_complete") == "Transcripción completada"
        assert manager.get_text("tray_menu.exit") == "Salir"
        
        # 3. Test config integration
        config = ConfigManager()
        with patch('InstanceScrubber.config_manager.set_locale') as mock_set_locale:
            mock_set_locale.return_value = True
            assert config.set_locale("es_ES") is True
            assert config.get("locale") == "es_ES"
