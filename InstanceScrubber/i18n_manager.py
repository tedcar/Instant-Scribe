"""Internationalization (i18n) Manager for Instant Scribe - Task 50

This module provides runtime language switching and string localization
capabilities for the Instant Scribe application.

Features:
- Load locale files from JSON
- Runtime language switching
- Fallback to English for missing translations
- String interpolation support
- Integration with ConfigManager for persistence
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = ["I18nManager", "get_text", "_"]


class I18nManager:
    """Manages internationalization and localization for the application."""
    
    def __init__(self, locale_dir: Path | str | None = None, default_locale: str = "en_US"):
        """Initialize the i18n manager.
        
        Args:
            locale_dir: Directory containing locale JSON files. Defaults to project locale/ dir.
            default_locale: Default locale to use when translations are missing.
        """
        if locale_dir is None:
            # Default to project locale directory
            locale_dir = Path(__file__).parent.parent / "locale"
        
        self.locale_dir = Path(locale_dir)
        self.default_locale = default_locale
        self.current_locale = default_locale
        self._translations: Dict[str, Dict[str, Any]] = {}
        self._logger = logging.getLogger(__name__)
        
        # Load default locale
        self._load_locale(default_locale)
    
    def set_locale(self, locale: str) -> bool:
        """Set the current locale.
        
        Args:
            locale: Locale code (e.g., 'en_US', 'es_ES')
            
        Returns:
            True if locale was successfully loaded, False otherwise.
        """
        if self._load_locale(locale):
            self.current_locale = locale
            self._logger.info("Locale changed to: %s", locale)
            return True
        return False
    
    def get_available_locales(self) -> list[str]:
        """Get list of available locale codes."""
        locales = []
        if self.locale_dir.exists():
            for file_path in self.locale_dir.glob("*.json"):
                locale_code = file_path.stem
                locales.append(locale_code)
        return sorted(locales)
    
    def get_text(self, key: str, **kwargs) -> str:
        """Get localized text for the given key.
        
        Args:
            key: Dot-separated key path (e.g., 'notifications.transcription_complete')
            **kwargs: Variables for string interpolation
            
        Returns:
            Localized text with variables interpolated, or the key if not found.
        """
        # Try current locale first
        text = self._get_text_from_locale(self.current_locale, key)
        
        # Fallback to default locale if not found
        if text is None and self.current_locale != self.default_locale:
            text = self._get_text_from_locale(self.default_locale, key)
        
        # If still not found, return the key itself
        if text is None:
            self._logger.warning("Missing translation for key: %s", key)
            text = key
        
        # Perform string interpolation if variables provided
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError) as exc:
                self._logger.warning("String interpolation failed for key %s: %s", key, exc)
        
        return text
    
    def _load_locale(self, locale: str) -> bool:
        """Load translations for the specified locale.
        
        Args:
            locale: Locale code to load
            
        Returns:
            True if successfully loaded, False otherwise.
        """
        locale_file = self.locale_dir / f"{locale}.json"
        
        if not locale_file.exists():
            self._logger.warning("Locale file not found: %s", locale_file)
            return False
        
        try:
            with locale_file.open("r", encoding="utf-8") as f:
                translations = json.load(f)
            
            self._translations[locale] = translations
            self._logger.debug("Loaded locale: %s", locale)
            return True
            
        except (json.JSONDecodeError, OSError) as exc:
            self._logger.error("Failed to load locale %s: %s", locale, exc)
            return False
    
    def _get_text_from_locale(self, locale: str, key: str) -> Optional[str]:
        """Get text from a specific locale.
        
        Args:
            locale: Locale code
            key: Dot-separated key path
            
        Returns:
            Localized text or None if not found.
        """
        if locale not in self._translations:
            return None
        
        # Navigate through nested dictionary using dot notation
        current = self._translations[locale]
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return str(current) if current is not None else None


# Global i18n manager instance
_global_i18n_manager: Optional[I18nManager] = None


def get_i18n_manager() -> I18nManager:
    """Get the global i18n manager instance."""
    global _global_i18n_manager
    if _global_i18n_manager is None:
        _global_i18n_manager = I18nManager()
    return _global_i18n_manager


def get_text(key: str, **kwargs) -> str:
    """Convenience function to get localized text.
    
    Args:
        key: Dot-separated key path
        **kwargs: Variables for string interpolation
        
    Returns:
        Localized text.
    """
    return get_i18n_manager().get_text(key, **kwargs)


def _(key: str, **kwargs) -> str:
    """Short alias for get_text() function.
    
    Args:
        key: Dot-separated key path
        **kwargs: Variables for string interpolation
        
    Returns:
        Localized text.
    """
    return get_text(key, **kwargs)


def set_locale(locale: str) -> bool:
    """Set the current locale globally.
    
    Args:
        locale: Locale code (e.g., 'en_US', 'es_ES')
        
    Returns:
        True if locale was successfully set, False otherwise.
    """
    return get_i18n_manager().set_locale(locale)


def get_available_locales() -> list[str]:
    """Get list of available locale codes."""
    return get_i18n_manager().get_available_locales()


def initialize_i18n(config_manager=None) -> None:
    """Initialize i18n system with configuration.
    
    Args:
        config_manager: ConfigManager instance to get locale preference from.
    """
    global _global_i18n_manager
    _global_i18n_manager = I18nManager()
    
    if config_manager:
        # Get locale from config, default to en_US
        locale = config_manager.get("locale", "en_US")
        _global_i18n_manager.set_locale(locale)
