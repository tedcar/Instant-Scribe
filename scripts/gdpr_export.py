#!/usr/bin/env python3
"""GDPR Data Export Script - Task 49.2

This script generates a comprehensive ZIP archive containing all user data
stored by Instant Scribe, fulfilling GDPR data portability requirements.

The export includes:
- All archived recordings and transcriptions
- Configuration files
- Application logs
- Temporary/recovery files
- Metadata about the export

Usage:
    python scripts/gdpr_export.py [--output-dir OUTPUT_DIR] [--include-logs]

The script automatically detects portable vs. installed mode and exports
data from the appropriate locations.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from InstanceScrubber.config_manager import ConfigManager
    from instant_scribe import portable_mode
except ImportError as exc:
    print(f"Error importing Instant Scribe modules: {exc}")
    print("Please run this script from the project root directory.")
    sys.exit(1)


class GDPRExporter:
    """Handles the export of all user data for GDPR compliance."""
    
    def __init__(self, output_dir: Path | None = None, include_logs: bool = False):
        self.output_dir = output_dir or Path.cwd()
        self.include_logs = include_logs
        self.config = ConfigManager()
        self.export_metadata: Dict[str, Any] = {
            "export_timestamp": datetime.now().isoformat(),
            "instant_scribe_version": "1.0.0",  # TODO: Get from version file
            "portable_mode": portable_mode.is_portable_mode() if portable_mode else False,
            "exported_data_types": [],
            "file_counts": {},
            "total_size_bytes": 0,
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)

    def export_all_data(self) -> Path:
        """Export all user data to a timestamped ZIP file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"instant_scribe_gdpr_export_{timestamp}.zip"
        zip_path = self.output_dir / zip_filename
        
        self.logger.info("Starting GDPR data export to: %s", zip_path)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            export_root = temp_path / "instant_scribe_export"
            export_root.mkdir()
            
            # Export each data category
            self._export_archived_recordings(export_root)
            self._export_configuration(export_root)
            self._export_temporary_files(export_root)
            
            if self.include_logs:
                self._export_logs(export_root)
            
            # Generate export metadata
            self._generate_metadata(export_root)
            
            # Create the final ZIP archive
            self._create_zip_archive(export_root, zip_path)
        
        self.logger.info("GDPR export completed successfully: %s", zip_path)
        return zip_path

    def _export_archived_recordings(self, export_root: Path) -> None:
        """Export all archived recordings and transcriptions."""
        archive_root = self._get_archive_directory()
        if not archive_root.exists():
            self.logger.info("No archived recordings found")
            return
        
        recordings_dir = export_root / "archived_recordings"
        recordings_dir.mkdir()
        
        file_count = 0
        total_size = 0
        
        for session_dir in archive_root.iterdir():
            if session_dir.is_dir():
                dest_session = recordings_dir / session_dir.name
                shutil.copytree(session_dir, dest_session)
                
                # Count files and calculate size
                for file_path in dest_session.rglob("*"):
                    if file_path.is_file():
                        file_count += 1
                        total_size += file_path.stat().st_size
        
        self.export_metadata["exported_data_types"].append("archived_recordings")
        self.export_metadata["file_counts"]["archived_recordings"] = file_count
        self.export_metadata["total_size_bytes"] += total_size
        
        self.logger.info("Exported %d archived recording files (%d bytes)", file_count, total_size)

    def _export_configuration(self, export_root: Path) -> None:
        """Export configuration files."""
        config_dir = export_root / "configuration"
        config_dir.mkdir()
        
        # Export main config file
        config_path = self.config._config_path
        if config_path.exists():
            shutil.copy2(config_path, config_dir / "config.json")
            
        # Export sanitized config (without sensitive data)
        sanitized_config = self._sanitize_config(self.config.settings)
        sanitized_path = config_dir / "config_sanitized.json"
        with sanitized_path.open("w", encoding="utf-8") as f:
            json.dump(sanitized_config, f, indent=2, ensure_ascii=False)
        
        file_count = len(list(config_dir.iterdir()))
        total_size = sum(f.stat().st_size for f in config_dir.iterdir() if f.is_file())
        
        self.export_metadata["exported_data_types"].append("configuration")
        self.export_metadata["file_counts"]["configuration"] = file_count
        self.export_metadata["total_size_bytes"] += total_size
        
        self.logger.info("Exported %d configuration files (%d bytes)", file_count, total_size)

    def _export_temporary_files(self, export_root: Path) -> None:
        """Export temporary/recovery files from spooler."""
        temp_dir = export_root / "temporary_files"
        temp_dir.mkdir()
        
        # Get spooler temp directory
        spooler_temp = self._get_spooler_temp_directory()
        if spooler_temp.exists():
            recovery_dir = temp_dir / "recovery_chunks"
            shutil.copytree(spooler_temp, recovery_dir)
            
            file_count = len(list(recovery_dir.rglob("*")))
            total_size = sum(f.stat().st_size for f in recovery_dir.rglob("*") if f.is_file())
            
            self.export_metadata["exported_data_types"].append("temporary_files")
            self.export_metadata["file_counts"]["temporary_files"] = file_count
            self.export_metadata["total_size_bytes"] += total_size
            
            self.logger.info("Exported %d temporary files (%d bytes)", file_count, total_size)
        else:
            self.logger.info("No temporary files found")

    def _export_logs(self, export_root: Path) -> None:
        """Export application logs."""
        logs_dir = export_root / "logs"
        logs_dir.mkdir()
        
        # Find log directory
        log_root = self._get_logs_directory()
        if log_root.exists():
            for log_file in log_root.glob("*.log"):
                shutil.copy2(log_file, logs_dir)
            
            file_count = len(list(logs_dir.iterdir()))
            total_size = sum(f.stat().st_size for f in logs_dir.iterdir() if f.is_file())
            
            self.export_metadata["exported_data_types"].append("logs")
            self.export_metadata["file_counts"]["logs"] = file_count
            self.export_metadata["total_size_bytes"] += total_size
            
            self.logger.info("Exported %d log files (%d bytes)", file_count, total_size)
        else:
            self.logger.info("No log files found")

    def _generate_metadata(self, export_root: Path) -> None:
        """Generate export metadata file."""
        metadata_path = export_root / "export_metadata.json"
        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(self.export_metadata, f, indent=2, ensure_ascii=False)
        
        # Also create a human-readable summary
        summary_path = export_root / "README.txt"
        with summary_path.open("w", encoding="utf-8") as f:
            f.write("Instant Scribe GDPR Data Export\n")
            f.write("=" * 35 + "\n\n")
            f.write(f"Export Date: {self.export_metadata['export_timestamp']}\n")
            f.write(f"Application Version: {self.export_metadata['instant_scribe_version']}\n")
            f.write(f"Portable Mode: {self.export_metadata['portable_mode']}\n\n")
            f.write("Exported Data Types:\n")
            for data_type in self.export_metadata["exported_data_types"]:
                file_count = self.export_metadata["file_counts"].get(data_type, 0)
                f.write(f"  - {data_type}: {file_count} files\n")
            f.write(f"\nTotal Size: {self.export_metadata['total_size_bytes']} bytes\n")

    def _create_zip_archive(self, source_dir: Path, zip_path: Path) -> None:
        """Create the final ZIP archive."""
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)

    def _get_archive_directory(self) -> Path:
        """Get the archive directory path."""
        archive_root = self.config.get("archive_root", "")
        if archive_root:
            return Path(os.path.expandvars(archive_root)).expanduser().resolve()
        return Path.home() / "Instant Scribe" / "archive"

    def _get_spooler_temp_directory(self) -> Path:
        """Get the spooler temporary directory path."""
        if portable_mode and portable_mode.is_portable_mode():
            return portable_mode.get_data_path("Instant Scribe") / "temp"
        
        if os.name == "nt":
            base_dir = Path(os.environ.get("APPDATA", Path.home()))
        else:
            base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        
        return base_dir / "Instant Scribe" / "temp"

    def _get_logs_directory(self) -> Path:
        """Get the logs directory path."""
        # Check project logs directory first
        project_logs = Path(__file__).parent.parent / "logs"
        if project_logs.exists():
            return project_logs
        
        # Fallback to system logs location
        if portable_mode and portable_mode.is_portable_mode():
            return portable_mode.get_data_path("Instant Scribe") / "logs"
        
        if os.name == "nt":
            base_dir = Path(os.environ.get("APPDATA", Path.home()))
        else:
            base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        
        return base_dir / "Instant Scribe" / "logs"

    def _sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from config for export."""
        sanitized = config.copy()
        
        # Remove potentially sensitive keys
        sensitive_keys = ["api_key", "token", "password", "secret"]
        for key in list(sanitized.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
        
        return sanitized


def main():
    """Main entry point for the GDPR export script."""
    parser = argparse.ArgumentParser(
        description="Export all Instant Scribe user data for GDPR compliance"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to save the export ZIP file (default: current directory)"
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Include application log files in the export"
    )
    
    args = parser.parse_args()
    
    try:
        exporter = GDPRExporter(output_dir=args.output_dir, include_logs=args.include_logs)
        export_path = exporter.export_all_data()
        print(f"GDPR export completed successfully: {export_path}")
        return 0
    except Exception as exc:
        print(f"Error during GDPR export: {exc}")
        logging.exception("GDPR export failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
