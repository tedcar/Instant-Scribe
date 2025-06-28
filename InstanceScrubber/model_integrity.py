"""Model Integrity Verification for Task 57.

This module implements SHA-256 checksum verification for the Parakeet model
to ensure model integrity without requiring internet connectivity. It stores
checksums in a manifest file and validates models during startup.

Key Features:
- SHA-256 checksum calculation and verification
- Offline model integrity checking
- Model manifest storage and management
- Startup validation with error handling
- Support for both cached and bundled models
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List
import time

try:
    from InstanceScrubber.resource_manager import resource_path
    _RESOURCE_MANAGER_AVAILABLE = True
except ImportError:
    _RESOURCE_MANAGER_AVAILABLE = False

__all__ = ["ModelIntegrityChecker", "ModelManifest", "verify_model_integrity", "validate_model_on_startup"]


@dataclass
class ModelFileInfo:
    """Information about a model file."""
    path: str
    size_bytes: int
    sha256: str
    last_modified: float


@dataclass
class ModelManifest:
    """Model integrity manifest."""
    model_name: str
    model_version: str
    huggingface_url: str
    verification_date: str
    files: List[ModelFileInfo]
    total_size_bytes: int
    manifest_version: str = "1.0"


class ModelIntegrityChecker:
    """Handles model integrity verification and manifest management."""
    
    DEFAULT_MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v2"
    MANIFEST_FILENAME = "model_manifest.json"
    
    def __init__(self, model_name: str = None):
        """Initialize model integrity checker.
        
        Args:
            model_name: Name of the model to verify (defaults to Parakeet)
        """
        self.model_name = model_name or self.DEFAULT_MODEL_NAME
        self._log = logging.getLogger(__name__)
        
    def _get_model_cache_paths(self) -> List[Path]:
        """Get potential model cache locations."""
        paths = []
        
        # Standard NeMo cache locations
        home = Path.home()
        
        # Windows
        if sys.platform == "win32":
            paths.extend([
                home / "AppData/Local/torch/NeMo/models",
                Path(os.environ.get("LOCALAPPDATA", "")) / "torch/NeMo/models",
            ])
        
        # Linux/macOS
        paths.extend([
            home / ".cache/torch/NeMo/models",
            Path("/tmp/torch/NeMo/models"),
        ])
        
        # Bundled model location (for portable apps)
        if _RESOURCE_MANAGER_AVAILABLE:
            try:
                bundled_path = resource_path("nemo_models")
                if bundled_path.exists():
                    paths.append(bundled_path)
            except Exception:
                pass
        
        return [p for p in paths if p.exists()]
    
    def _find_model_files(self) -> List[Path]:
        """Find all files belonging to the model."""
        model_files = []
        
        for cache_path in self._get_model_cache_paths():
            self._log.debug(f"Searching for model files in: {cache_path}")
            
            # Look for directories containing "parakeet"
            for item in cache_path.iterdir():
                if item.is_dir() and "parakeet" in item.name.lower():
                    self._log.debug(f"Found potential model directory: {item}")
                    
                    # Collect all files in the model directory
                    for file_path in item.rglob("*"):
                        if file_path.is_file():
                            model_files.append(file_path)
                            
                # Also check for .nemo files directly
                elif item.is_file() and item.suffix == ".nemo" and "parakeet" in item.name.lower():
                    model_files.append(item)
        
        return model_files
    
    def _calculate_file_sha256(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as exc:
            self._log.error(f"Failed to calculate SHA-256 for {file_path}: {exc}")
            raise
    
    def _get_manifest_path(self) -> Path:
        """Get the path to the model manifest file."""
        # Try to store manifest near the model files
        cache_paths = self._get_model_cache_paths()
        if cache_paths:
            return cache_paths[0].parent / self.MANIFEST_FILENAME
        
        # Fallback to application data directory
        if _RESOURCE_MANAGER_AVAILABLE:
            try:
                return resource_path("data") / self.MANIFEST_FILENAME
            except Exception:
                pass
        
        # Final fallback to current directory
        return Path(self.MANIFEST_FILENAME)
    
    def generate_manifest(self) -> ModelManifest:
        """Generate a new model integrity manifest."""
        self._log.info(f"Generating integrity manifest for {self.model_name}")
        
        model_files = self._find_model_files()
        if not model_files:
            raise FileNotFoundError(f"No model files found for {self.model_name}")
        
        self._log.info(f"Found {len(model_files)} model files")
        
        file_infos = []
        total_size = 0
        
        for file_path in model_files:
            self._log.debug(f"Processing file: {file_path}")
            
            try:
                stat = file_path.stat()
                sha256 = self._calculate_file_sha256(file_path)
                
                file_info = ModelFileInfo(
                    path=str(file_path),
                    size_bytes=stat.st_size,
                    sha256=sha256,
                    last_modified=stat.st_mtime
                )
                
                file_infos.append(file_info)
                total_size += stat.st_size
                
                self._log.debug(f"File {file_path.name}: {stat.st_size} bytes, SHA-256: {sha256[:16]}...")
                
            except Exception as exc:
                self._log.error(f"Failed to process file {file_path}: {exc}")
                raise
        
        manifest = ModelManifest(
            model_name=self.model_name,
            model_version="0.6b-v2",  # Parakeet version
            huggingface_url="https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2",
            verification_date=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            files=file_infos,
            total_size_bytes=total_size
        )
        
        self._log.info(f"Generated manifest with {len(file_infos)} files, total size: {total_size:,} bytes")
        return manifest
    
    def save_manifest(self, manifest: ModelManifest) -> Path:
        """Save model manifest to disk."""
        manifest_path = self._get_manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(manifest), f, indent=2, ensure_ascii=False)
            
            self._log.info(f"Saved model manifest to: {manifest_path}")
            return manifest_path
            
        except Exception as exc:
            self._log.error(f"Failed to save manifest to {manifest_path}: {exc}")
            raise
    
    def load_manifest(self) -> Optional[ModelManifest]:
        """Load existing model manifest."""
        manifest_path = self._get_manifest_path()
        
        if not manifest_path.exists():
            self._log.debug(f"No manifest found at: {manifest_path}")
            return None
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert file info dictionaries back to dataclasses
            files = [ModelFileInfo(**file_data) for file_data in data['files']]
            data['files'] = files
            
            manifest = ModelManifest(**data)
            self._log.debug(f"Loaded manifest from: {manifest_path}")
            return manifest
            
        except Exception as exc:
            self._log.error(f"Failed to load manifest from {manifest_path}: {exc}")
            return None
    
    def verify_model_integrity(self, manifest: ModelManifest = None) -> bool:
        """Verify model integrity against manifest.
        
        Args:
            manifest: Manifest to verify against (loads from disk if None)
            
        Returns:
            True if all files pass integrity check, False otherwise
        """
        if manifest is None:
            manifest = self.load_manifest()
            if manifest is None:
                self._log.warning("No manifest available for verification")
                return False
        
        self._log.info(f"Verifying integrity of {len(manifest.files)} model files")
        
        failed_files = []
        missing_files = []
        
        for file_info in manifest.files:
            file_path = Path(file_info.path)
            
            if not file_path.exists():
                missing_files.append(str(file_path))
                self._log.error(f"Model file missing: {file_path}")
                continue
            
            try:
                # Check file size
                current_size = file_path.stat().st_size
                if current_size != file_info.size_bytes:
                    failed_files.append(f"{file_path} (size mismatch: {current_size} vs {file_info.size_bytes})")
                    continue
                
                # Check SHA-256
                current_sha256 = self._calculate_file_sha256(file_path)
                if current_sha256 != file_info.sha256:
                    failed_files.append(f"{file_path} (checksum mismatch)")
                    self._log.error(f"Checksum mismatch for {file_path}: {current_sha256} vs {file_info.sha256}")
                    continue
                
                self._log.debug(f"File verified: {file_path.name}")
                
            except Exception as exc:
                failed_files.append(f"{file_path} (verification error: {exc})")
                self._log.error(f"Error verifying {file_path}: {exc}")
        
        # Report results
        if missing_files:
            self._log.error(f"Missing files: {missing_files}")
        
        if failed_files:
            self._log.error(f"Failed verification: {failed_files}")
        
        success = len(missing_files) == 0 and len(failed_files) == 0
        
        if success:
            self._log.info("Model integrity verification passed")
        else:
            self._log.error("Model integrity verification failed")
        
        return success
    
    def ensure_model_integrity(self) -> bool:
        """Ensure model integrity, generating manifest if needed.
        
        Returns:
            True if model integrity is verified, False otherwise
        """
        # Try to load existing manifest
        manifest = self.load_manifest()
        
        if manifest is None:
            self._log.info("No existing manifest found, generating new one")
            try:
                manifest = self.generate_manifest()
                self.save_manifest(manifest)
                return True  # Newly generated manifest is assumed valid
            except Exception as exc:
                self._log.error(f"Failed to generate manifest: {exc}")
                return False
        
        # Verify against existing manifest
        return self.verify_model_integrity(manifest)


def verify_model_integrity(model_name: str = None,
                          generate_if_missing: bool = True) -> bool:
    """Convenience function to verify model integrity.

    Args:
        model_name: Name of model to verify
        generate_if_missing: Generate manifest if missing

    Returns:
        True if verification passes, False otherwise
    """
    checker = ModelIntegrityChecker(model_name)

    if generate_if_missing:
        return checker.ensure_model_integrity()
    else:
        manifest = checker.load_manifest()
        if manifest is None:
            return False
        return checker.verify_model_integrity(manifest)


def validate_model_on_startup(model_name: str = None,
                             abort_on_failure: bool = True) -> bool:
    """Validate model integrity during application startup.

    This function is designed to be called during application initialization
    to ensure the model is valid before attempting to load it. If validation
    fails and abort_on_failure is True, it will show an error message and
    suggest re-downloading the model.

    Args:
        model_name: Name of model to validate
        abort_on_failure: Whether to show error dialog and suggest re-download

    Returns:
        True if validation passes, False otherwise
    """
    logger = logging.getLogger(__name__)

    try:
        checker = ModelIntegrityChecker(model_name)

        # Try to load existing manifest
        manifest = checker.load_manifest()

        if manifest is None:
            logger.info("No model manifest found - model integrity cannot be verified")
            if abort_on_failure:
                _show_model_integrity_error(
                    "Model integrity manifest not found",
                    "The model integrity manifest is missing. This may indicate the model "
                    "was not properly downloaded or the cache was corrupted.\n\n"
                    "Please re-download the model by restarting the application with an "
                    "internet connection."
                )
                return False
            return True  # Allow startup without manifest

        # Verify model integrity
        logger.info("Validating model integrity during startup...")
        is_valid = checker.verify_model_integrity(manifest)

        if not is_valid:
            logger.error("Model integrity validation failed during startup")
            if abort_on_failure:
                _show_model_integrity_error(
                    "Model integrity validation failed",
                    "The model files have been corrupted or modified. This can happen "
                    "due to storage device errors, incomplete downloads, or file system issues.\n\n"
                    "Please re-download the model by deleting the model cache and "
                    "restarting the application with an internet connection.\n\n"
                    f"Model cache locations:\n"
                    f"• Windows: %LOCALAPPDATA%\\torch\\NeMo\\models\n"
                    f"• Linux/macOS: ~/.cache/torch/NeMo/models"
                )
                return False
        else:
            logger.info("Model integrity validation passed")

        return is_valid

    except Exception as exc:
        logger.error(f"Error during model integrity validation: {exc}")
        if abort_on_failure:
            _show_model_integrity_error(
                "Model integrity validation error",
                f"An error occurred while validating model integrity:\n\n{exc}\n\n"
                "This may indicate a problem with the model cache or file system. "
                "Please try restarting the application."
            )
            return False
        return True  # Allow startup on validation errors


def _show_model_integrity_error(title: str, message: str) -> None:
    """Show model integrity error dialog."""
    logger = logging.getLogger(__name__)

    try:
        # Try to show notification using the notification manager
        from InstanceScrubber.notification_manager import NotificationManager
        notifier = NotificationManager(show_notifications=True)

        notifier.show_blocking_notification(
            title=f"Instant Scribe - {title}",
            message=message,
            buttons=["OK"]
        )

    except Exception as exc:
        logger.error(f"Failed to show integrity error dialog: {exc}")
        # Fallback to console output
        print(f"\n{'='*60}")
        print(f"INSTANT SCRIBE - {title.upper()}")
        print(f"{'='*60}")
        print(message)
        print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Model Integrity Verification")
    parser.add_argument("--model", default="nvidia/parakeet-tdt-0.6b-v2", help="Model name")
    parser.add_argument("--generate", action="store_true", help="Generate new manifest")
    parser.add_argument("--verify", action="store_true", help="Verify existing manifest")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    checker = ModelIntegrityChecker(args.model)
    
    if args.generate:
        try:
            manifest = checker.generate_manifest()
            manifest_path = checker.save_manifest(manifest)
            print(f"Generated manifest: {manifest_path}")
            sys.exit(0)
        except Exception as exc:
            print(f"Failed to generate manifest: {exc}")
            sys.exit(1)
    
    elif args.verify:
        success = checker.verify_model_integrity()
        sys.exit(0 if success else 1)
    
    else:
        # Default: ensure integrity
        success = checker.ensure_model_integrity()
        sys.exit(0 if success else 1)
