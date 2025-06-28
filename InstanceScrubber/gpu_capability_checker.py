"""GPU capability validation for Task 47 - GPU Capability Fallback.

This module provides functionality to detect GPU VRAM availability and validate
that the system meets the minimum requirements for running Instant Scribe.

Key features:
- Detects total and free VRAM on NVIDIA GPUs
- Validates minimum 3 GB free VRAM requirement
- Provides blocking notifications for unsupported hardware
- Gracefully handles systems without NVIDIA GPUs or pynvml
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple
import sys

try:
    import pynvml  # type: ignore
    _NVML_AVAILABLE = True
except ImportError:  # pragma: no cover – headless CI path
    pynvml = None  # type: ignore
    _NVML_AVAILABLE = False

__all__ = ["GPUCapabilityChecker", "check_gpu_capability_blocking"]


class GPUCapabilityChecker:
    """Validates GPU VRAM capability for Instant Scribe requirements.
    
    This class checks if the system has sufficient VRAM (minimum 3 GB free)
    to run the Parakeet ASR model effectively. It provides both programmatic
    checking and user-facing blocking notifications.
    """
    
    MINIMUM_VRAM_GB = 3.0  # Minimum free VRAM required in GB
    
    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._handle: Optional[object] = None
        self._init_nvml()
    
    def _init_nvml(self) -> None:
        """Initialize NVML for GPU monitoring."""
        if not _NVML_AVAILABLE:
            self._log.info("pynvml not available – GPU capability checking disabled")
            return
        
        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._log.debug("NVML initialized successfully")
        except Exception as exc:  # pragma: no cover – unsupported host
            self._log.info("NVML initialization failed – GPU capability checking disabled: %s", exc)
            self._handle = None
    
    def get_gpu_memory_info(self) -> Optional[Tuple[float, float, float]]:
        """Get GPU memory information.
        
        Returns:
            Tuple of (total_gb, used_gb, free_gb) or None if unavailable.
        """
        if self._handle is None:
            return None
        
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)  # type: ignore[attr-defined]
            total_gb = mem.total / (1024 ** 3)
            used_gb = mem.used / (1024 ** 3)
            free_gb = mem.free / (1024 ** 3)
            return (total_gb, used_gb, free_gb)
        except Exception as exc:  # pragma: no cover – NVML runtime error
            self._log.debug("nvmlDeviceGetMemoryInfo failed: %s", exc)
            return None
    
    def get_gpu_name(self) -> Optional[str]:
        """Get the name of the primary GPU.
        
        Returns:
            GPU name string or None if unavailable.
        """
        if self._handle is None:
            return None
        
        try:
            name = pynvml.nvmlDeviceGetName(self._handle)  # type: ignore[attr-defined]
            if isinstance(name, bytes):
                return name.decode('utf-8')
            return str(name)
        except Exception as exc:  # pragma: no cover – NVML runtime error
            self._log.debug("nvmlDeviceGetName failed: %s", exc)
            return None
    
    def check_vram_capability(self) -> Tuple[bool, str]:
        """Check if the GPU meets minimum VRAM requirements.
        
        Returns:
            Tuple of (is_capable, message) where is_capable indicates if the
            system meets requirements and message provides details.
        """
        memory_info = self.get_gpu_memory_info()
        gpu_name = self.get_gpu_name()
        
        if memory_info is None:
            return False, "No NVIDIA GPU detected or NVML unavailable"
        
        total_gb, used_gb, free_gb = memory_info
        gpu_display = gpu_name or "Unknown GPU"
        
        self._log.info(
            "GPU: %s - Total: %.2f GB, Used: %.2f GB, Free: %.2f GB",
            gpu_display, total_gb, used_gb, free_gb
        )
        
        if free_gb < self.MINIMUM_VRAM_GB:
            message = (
                f"Insufficient VRAM: {gpu_display} has {free_gb:.2f} GB free, "
                f"but Instant Scribe requires at least {self.MINIMUM_VRAM_GB} GB free VRAM"
            )
            return False, message
        
        message = (
            f"GPU capability OK: {gpu_display} has {free_gb:.2f} GB free VRAM "
            f"(>= {self.MINIMUM_VRAM_GB} GB required)"
        )
        return True, message


def check_gpu_capability_blocking() -> bool:
    """Perform blocking GPU capability check with user notification.
    
    This function checks GPU VRAM capability and displays a blocking
    notification if requirements are not met. It's designed to be called
    during application startup to prevent running on unsupported hardware.
    
    Returns:
        True if GPU meets requirements, False otherwise.
    """
    checker = GPUCapabilityChecker()
    is_capable, message = checker.check_vram_capability()
    
    if not is_capable:
        # Log the issue
        logging.error("GPU capability check failed: %s", message)
        
        # Try to show blocking notification
        try:
            from InstanceScrubber.notification_manager import NotificationManager
            notifier = NotificationManager(show_notifications=True)
            
            # Show blocking notification
            notifier.show_blocking_notification(
                title="Instant Scribe - Unsupported Hardware",
                message=message + "\n\nThe application will now exit.",
                buttons=["OK"]
            )
        except Exception as exc:
            logging.warning("Failed to show blocking notification: %s", exc)
            # Fallback to console output
            print(f"\nERROR: {message}")
            print("The application will now exit.")
            input("Press Enter to continue...")
        
        return False
    
    # Log success
    logging.info("GPU capability check passed: %s", message)
    return True
