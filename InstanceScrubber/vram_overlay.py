"""Live VRAM Overlay - Task 53

This module provides a small on-screen overlay showing live VRAM usage percentage.
The overlay can be toggled via hotkey (Ctrl+Alt+F7) and integrates with the existing
pynvml polling loop from Task 33.

Key features:
- Lightweight tkinter-based overlay window
- Always-on-top, semi-transparent display
- Real-time VRAM percentage updates
- Hotkey toggle support (Ctrl+Alt+F7)
- Integration with existing GPUResourceMonitor
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Optional, Callable, Any
import time

try:
    import pynvml  # type: ignore
    _NVML_AVAILABLE = True
except ImportError:  # pragma: no cover – headless CI path
    pynvml = None  # type: ignore
    _NVML_AVAILABLE = False

__all__ = ["VRAMOverlay"]


class VRAMOverlay:
    """On-screen VRAM usage overlay with hotkey toggle support.
    
    This class creates a small, semi-transparent window that displays current
    VRAM usage as a percentage. The overlay can be toggled on/off via hotkey
    and integrates with the existing GPU monitoring infrastructure.
    """
    
    def __init__(self, gpu_monitor: Any):
        """Initialize the VRAM overlay.
        
        Args:
            gpu_monitor: Instance of GPUResourceMonitor for VRAM data
        """
        self._gpu_monitor = gpu_monitor
        self._log = logging.getLogger(self.__class__.__name__)
        
        # UI state
        self._root: Optional[tk.Tk] = None
        self._label: Optional[tk.Label] = None
        self._visible = False
        self._ui_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # VRAM data
        self._current_vram_percent = 0.0
        self._last_update = 0.0
        
        # Update interval (seconds)
        self._update_interval = 1.0
        
    def toggle_visibility(self) -> None:
        """Toggle overlay visibility on/off."""
        if self._visible:
            self.hide()
        else:
            self.show()
    
    def show(self) -> None:
        """Show the VRAM overlay."""
        if self._visible:
            self._log.debug("VRAM overlay already visible")
            return
            
        self._visible = True
        self._stop_event.clear()
        
        # Start UI thread
        self._ui_thread = threading.Thread(target=self._run_ui, daemon=True)
        self._ui_thread.start()
        
        self._log.info("VRAM overlay shown")
    
    def hide(self) -> None:
        """Hide the VRAM overlay."""
        if not self._visible:
            self._log.debug("VRAM overlay already hidden")
            return
            
        self._visible = False
        self._stop_event.set()
        
        # Close UI in thread-safe manner
        if self._root:
            self._root.after(0, self._close_ui)
        
        self._log.info("VRAM overlay hidden")
    
    def update_vram_data(self, used_mb: float, total_mb: float) -> None:
        """Update VRAM data for display.
        
        Args:
            used_mb: Used VRAM in megabytes
            total_mb: Total VRAM in megabytes
        """
        if total_mb > 0:
            self._current_vram_percent = (used_mb / total_mb) * 100.0
        else:
            self._current_vram_percent = 0.0
        
        self._last_update = time.time()
        
        # Update UI if visible
        if self._visible and self._label:
            self._root.after(0, self._update_display)
    
    def _run_ui(self) -> None:
        """Run the tkinter UI loop in a separate thread."""
        try:
            self._create_ui()
            self._root.mainloop()
        except Exception as exc:
            self._log.error("VRAM overlay UI error: %s", exc)
        finally:
            self._cleanup_ui()
    
    def _create_ui(self) -> None:
        """Create the overlay UI components."""
        self._root = tk.Tk()
        self._root.title("VRAM Monitor")
        
        # Configure window properties
        self._root.attributes('-topmost', True)  # Always on top
        self._root.attributes('-alpha', 0.8)     # Semi-transparent
        self._root.overrideredirect(True)        # Remove window decorations
        
        # Position in top-right corner
        self._root.geometry("120x40+{}+10".format(self._root.winfo_screenwidth() - 140))
        
        # Create label for VRAM display
        self._label = tk.Label(
            self._root,
            text="VRAM: ---%",
            font=("Arial", 10, "bold"),
            bg="black",
            fg="lime",
            padx=10,
            pady=5
        )
        self._label.pack(fill=tk.BOTH, expand=True)
        
        # Bind click to hide overlay
        self._label.bind("<Button-1>", lambda e: self.hide())
        
        # Start update loop
        self._schedule_update()
    
    def _update_display(self) -> None:
        """Update the VRAM percentage display."""
        if not self._label or not self._visible:
            return
        
        # Check if data is recent (within 5 seconds)
        data_age = time.time() - self._last_update
        if data_age > 5.0:
            text = "VRAM: ---%"
            color = "gray"
        else:
            text = f"VRAM: {self._current_vram_percent:.0f}%"
            # Color coding: green < 70%, yellow < 90%, red >= 90%
            if self._current_vram_percent < 70:
                color = "lime"
            elif self._current_vram_percent < 90:
                color = "yellow"
            else:
                color = "red"
        
        self._label.config(text=text, fg=color)
    
    def _schedule_update(self) -> None:
        """Schedule the next display update."""
        if self._visible and self._root:
            self._update_display()
            self._root.after(int(self._update_interval * 1000), self._schedule_update)
    
    def _close_ui(self) -> None:
        """Close the UI window."""
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception as exc:
                self._log.debug("Error closing VRAM overlay UI: %s", exc)
    
    def _cleanup_ui(self) -> None:
        """Clean up UI resources."""
        self._root = None
        self._label = None
        self._ui_thread = None
    
    @property
    def is_visible(self) -> bool:
        """Check if overlay is currently visible."""
        return self._visible
    
    def get_vram_percent(self) -> float:
        """Get current VRAM usage percentage."""
        return self._current_vram_percent
