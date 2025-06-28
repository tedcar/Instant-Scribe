"""Tests for Task 53: Live VRAM Overlay

Tests both VRAM overlay functionality (53.1) and pynvml integration (53.2).
"""

from __future__ import annotations

import pytest
import time
import threading
from unittest.mock import patch, MagicMock, Mock
import sys

# Mock tkinter before importing VRAMOverlay
class MockTk:
    def __init__(self):
        self.attributes_calls = []
        self.geometry_calls = []
        self.title_calls = []
        self.after_calls = []
        self.quit_called = False
        self.destroy_called = False
        self.mainloop_called = False
        
    def attributes(self, *args):
        self.attributes_calls.append(args)
        
    def geometry(self, *args):
        self.geometry_calls.append(args)
        
    def title(self, *args):
        self.title_calls.append(args)
        
    def after(self, delay, callback):
        self.after_calls.append((delay, callback))
        # Execute callback immediately for testing
        if callback:
            try:
                callback()
            except Exception:
                pass
        
    def quit(self):
        self.quit_called = True
        
    def destroy(self):
        self.destroy_called = True
        
    def mainloop(self):
        self.mainloop_called = True
        
    def winfo_screenwidth(self):
        return 1920

class MockLabel:
    def __init__(self, *args, **kwargs):
        self.config_calls = []
        self.bind_calls = []
        self.pack_calls = []
        
    def config(self, **kwargs):
        self.config_calls.append(kwargs)
        
    def bind(self, event, callback):
        self.bind_calls.append((event, callback))
        
    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

# Mock tkinter module
mock_tkinter = MagicMock()
mock_tkinter.Tk = MockTk
mock_tkinter.Label = MockLabel
mock_tkinter.BOTH = "both"
mock_tkinter.TRUE = True

sys.modules['tkinter'] = mock_tkinter

from InstanceScrubber.vram_overlay import VRAMOverlay


class TestVRAMOverlay:
    """Test VRAM overlay functionality."""

    @pytest.fixture
    def mock_gpu_monitor(self):
        """Create a mock GPU monitor."""
        return MagicMock()

    @pytest.fixture
    def vram_overlay(self, mock_gpu_monitor):
        """Create a VRAM overlay instance."""
        return VRAMOverlay(mock_gpu_monitor)

    def test_vram_overlay_initialization(self, vram_overlay, mock_gpu_monitor):
        """Test VRAM overlay initializes correctly."""
        assert vram_overlay._gpu_monitor is mock_gpu_monitor
        assert vram_overlay._visible is False
        assert vram_overlay._current_vram_percent == 0.0
        assert vram_overlay._update_interval == 1.0

    def test_vram_overlay_show_hide(self, vram_overlay):
        """Test showing and hiding the overlay."""
        # Initially hidden
        assert not vram_overlay.is_visible
        
        # Show overlay
        with patch('threading.Thread') as mock_thread:
            vram_overlay.show()
            assert vram_overlay.is_visible
            mock_thread.assert_called_once()
        
        # Hide overlay
        vram_overlay.hide()
        assert not vram_overlay.is_visible

    def test_vram_overlay_toggle_visibility(self, vram_overlay):
        """Test toggling overlay visibility."""
        # Initially hidden, toggle should show
        with patch('threading.Thread'):
            vram_overlay.toggle_visibility()
            assert vram_overlay.is_visible
        
        # Now visible, toggle should hide
        vram_overlay.toggle_visibility()
        assert not vram_overlay.is_visible

    def test_vram_data_update(self, vram_overlay):
        """Test updating VRAM data."""
        # Update with valid data
        vram_overlay.update_vram_data(4000, 8000)  # 50% usage
        assert vram_overlay.get_vram_percent() == 50.0
        
        # Update with zero total (edge case)
        vram_overlay.update_vram_data(1000, 0)
        assert vram_overlay.get_vram_percent() == 0.0
        
        # Update with 100% usage
        vram_overlay.update_vram_data(8000, 8000)
        assert vram_overlay.get_vram_percent() == 100.0

    def test_vram_overlay_ui_creation(self, vram_overlay):
        """Test UI creation and configuration."""
        # Mock the UI creation
        with patch.object(vram_overlay, '_create_ui') as mock_create:
            with patch('threading.Thread') as mock_thread:
                vram_overlay.show()
                mock_thread.assert_called_once()
                
                # Simulate thread execution
                thread_target = mock_thread.call_args[1]['target']
                thread_target()
                mock_create.assert_called_once()

    def test_vram_overlay_display_update(self, vram_overlay):
        """Test display update with different VRAM levels."""
        # Set up mock UI components
        vram_overlay._root = MockTk()
        vram_overlay._label = MockLabel()
        vram_overlay._visible = True
        
        # Test low VRAM (green)
        vram_overlay.update_vram_data(2000, 8000)  # 25%
        vram_overlay._update_display()
        
        # Test medium VRAM (yellow)
        vram_overlay.update_vram_data(6000, 8000)  # 75%
        vram_overlay._update_display()
        
        # Test high VRAM (red)
        vram_overlay.update_vram_data(7500, 8000)  # 93.75%
        vram_overlay._update_display()
        
        # Check that config was called
        assert len(vram_overlay._label.config_calls) >= 3

    def test_vram_overlay_stale_data(self, vram_overlay):
        """Test handling of stale VRAM data."""
        # Set up mock UI components
        vram_overlay._root = MockTk()
        vram_overlay._label = MockLabel()
        vram_overlay._visible = True
        
        # Set old timestamp
        vram_overlay._last_update = time.time() - 10  # 10 seconds ago
        vram_overlay._update_display()
        
        # Should show "---%" for stale data
        config_calls = vram_overlay._label.config_calls
        assert any("---%" in str(call) for call in config_calls)


class TestVRAMOverlayIntegration:
    """Integration tests for VRAM overlay with ApplicationOrchestrator."""

    def test_vram_overlay_hotkey_integration(self):
        """Test VRAM overlay hotkey integration."""
        from instant_scribe.application_orchestrator import ApplicationOrchestrator
        
        # Create orchestrator with stub worker
        orch = ApplicationOrchestrator(use_stub_worker=True)
        
        # Check that VRAM overlay is initialized
        assert hasattr(orch, 'vram_overlay')
        assert hasattr(orch, 'vram_overlay_hotkey_manager')
        
        # Check that toggle method exists
        assert hasattr(orch, '_toggle_vram_overlay')
        
        # Test toggle method (should not crash)
        if orch.vram_overlay:
            orch._toggle_vram_overlay()

    def test_vram_overlay_gpu_monitor_integration(self):
        """Test VRAM overlay integration with GPU monitor."""
        from instant_scribe.application_orchestrator import ApplicationOrchestrator
        
        # Create orchestrator with stub worker
        orch = ApplicationOrchestrator(use_stub_worker=True)
        orch.start()
        
        try:
            # Check that GPU monitor can update overlay
            if orch.vram_overlay and orch.gpu_monitor:
                # Simulate VRAM data update
                orch.vram_overlay.update_vram_data(4000, 8000)
                assert orch.vram_overlay.get_vram_percent() == 50.0
                
                # Test GPU monitor check (should not crash)
                orch.gpu_monitor.check_once()
        finally:
            orch.shutdown()

    def test_vram_overlay_config_defaults(self):
        """Test VRAM overlay configuration defaults."""
        from instant_scribe.config_manager import ConfigManager
        
        config = ConfigManager()
        
        # Check that VRAM overlay hotkey is configured
        assert "vram_overlay_hotkey" in config.DEFAULTS
        assert config.get("vram_overlay_hotkey") == "ctrl+alt+f7"


def test_task53_integration():
    """Integration test for Task 53: Complete VRAM overlay workflow."""
    from instant_scribe.application_orchestrator import ApplicationOrchestrator
    
    # Create and start orchestrator
    orch = ApplicationOrchestrator(use_stub_worker=True)
    orch.start()
    
    try:
        # Test VRAM overlay functionality
        if orch.vram_overlay:
            # Test initial state
            assert not orch.vram_overlay.is_visible
            
            # Test toggle via method
            orch._toggle_vram_overlay()
            # Note: In test environment, overlay may not actually show due to tkinter mocking
            
            # Test VRAM data update
            orch.vram_overlay.update_vram_data(3000, 8000)  # 37.5%
            assert orch.vram_overlay.get_vram_percent() == 37.5
            
            # Test hide
            orch.vram_overlay.hide()
            assert not orch.vram_overlay.is_visible
        
        # Test GPU monitor integration
        if orch.gpu_monitor:
            # Should not crash when checking
            orch.gpu_monitor.check_once()
            
    finally:
        orch.shutdown()


if __name__ == "__main__":
    # Run the integration test directly
    test_task53_integration()
    print("Task 53 integration test completed successfully!")
