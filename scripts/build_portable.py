#!/usr/bin/env python3
"""Build portable ZIP distribution for Instant Scribe.

This script creates a portable ZIP distribution that:
1. Uses the existing PyInstaller build from Task 15
2. Adds a portable.txt marker file
3. Creates a portable-friendly directory structure
4. Skips registry writes and uses relative paths

Usage:
    python scripts/build_portable.py [--output-dir OUTPUT_DIR]

The script depends on Task 15 (PyInstaller packaging) being completed first.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Optional


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Build portable ZIP distribution for Instant Scribe",
        epilog="This script requires the PyInstaller build from Task 15 to be completed first."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist"),
        help="Output directory for the portable ZIP file (default: dist)"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("dist/Instant Scribe"),
        help="Source directory containing the PyInstaller build (default: dist/Instant Scribe)"
    )
    parser.add_argument(
        "--zip-name",
        type=str,
        default="Instant_Scribe_Portable.zip",
        help="Name of the output ZIP file (default: Instant_Scribe_Portable.zip)"
    )
    return parser.parse_args()


def verify_pyinstaller_build(source_dir: Path) -> None:
    """Verify that the PyInstaller build exists and is complete."""
    if not source_dir.exists():
        raise FileNotFoundError(
            f"PyInstaller build directory not found: {source_dir}\n"
            "Please run 'pyinstaller InstantScribe.spec' first (Task 15)."
        )
    
    executable = source_dir / "Instant Scribe.exe"
    if not executable.exists():
        raise FileNotFoundError(
            f"Main executable not found: {executable}\n"
            "The PyInstaller build appears to be incomplete."
        )
    
    print(f"✓ PyInstaller build verified at: {source_dir}")


def create_portable_structure(source_dir: Path, temp_dir: Path) -> None:
    """Create the portable directory structure."""
    print("Creating portable directory structure...")
    
    # Copy the entire PyInstaller build
    shutil.copytree(source_dir, temp_dir, dirs_exist_ok=True)
    
    # Create the portable marker file
    portable_marker = temp_dir / "portable.txt"
    with open(portable_marker, "w", encoding="utf-8") as f:
        f.write("This file indicates that Instant Scribe is running in portable mode.\n")
        f.write("All configuration and data files will be stored in the 'data' subdirectory.\n")
        f.write("Delete this file to switch back to standard installation mode.\n")
        f.write("\n")
        f.write("Portable Mode Features:\n")
        f.write("- No registry writes\n")
        f.write("- All data stored relative to executable\n")
        f.write("- Can be run from any location\n")
        f.write("- No installation required\n")
    
    # Create the data directory structure
    data_dir = temp_dir / "data"
    data_subdirs = [
        "temp",      # For audio spooling
        "archives",  # For recording archives
        "logs",      # For application logs
        "reports",   # For crash reports
        "metrics",   # For telemetry data
    ]
    
    for subdir in data_subdirs:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    # Create a README for the data directory
    data_readme = data_dir / "README.txt"
    with open(data_readme, "w", encoding="utf-8") as f:
        f.write("Instant Scribe Portable Mode Data Directory\n")
        f.write("=" * 45 + "\n\n")
        f.write("This directory contains all user data for Instant Scribe in portable mode:\n\n")
        f.write("- config.json: Application configuration\n")
        f.write("- temp/: Temporary audio files during recording\n")
        f.write("- archives/: Completed recording sessions\n")
        f.write("- logs/: Application log files\n")
        f.write("- reports/: Crash reports (if any)\n")
        f.write("- metrics/: Telemetry data (if enabled)\n\n")
        f.write("You can safely backup this entire directory to preserve your settings and recordings.\n")
    
    print(f"✓ Portable structure created in: {temp_dir}")


def create_portable_zip(temp_dir: Path, output_path: Path) -> None:
    """Create the portable ZIP file."""
    print(f"Creating portable ZIP: {output_path}")
    
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in temp_dir.rglob("*"):
            if file_path.is_file():
                # Calculate relative path for the ZIP archive
                arc_path = file_path.relative_to(temp_dir)
                zf.write(file_path, arc_path)
    
    # Get ZIP file size for reporting
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"✓ Portable ZIP created: {output_path} ({size_mb:.1f} MB)")


def create_portable_readme(output_dir: Path) -> None:
    """Create a README file for the portable distribution."""
    readme_path = output_dir / "Instant_Scribe_Portable_README.txt"
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("Instant Scribe Portable Distribution\n")
        f.write("=" * 37 + "\n\n")
        f.write("This is a portable version of Instant Scribe that can be run from any location\n")
        f.write("without installation. Simply extract the ZIP file and run 'Instant Scribe.exe'.\n\n")
        f.write("FEATURES:\n")
        f.write("- No installation required\n")
        f.write("- No registry writes\n")
        f.write("- All data stored relative to executable\n")
        f.write("- Can be run from USB drives or network locations\n")
        f.write("- Fully self-contained\n\n")
        f.write("REQUIREMENTS:\n")
        f.write("- Windows 10 or later\n")
        f.write("- NVIDIA GPU with CUDA support (RTX 3050 or better recommended)\n")
        f.write("- At least 4 GB free disk space\n")
        f.write("- Microphone for audio input\n\n")
        f.write("USAGE:\n")
        f.write("1. Extract the ZIP file to any location\n")
        f.write("2. Run 'Instant Scribe.exe'\n")
        f.write("3. The application will start in portable mode automatically\n")
        f.write("4. All configuration and data will be stored in the 'data' subdirectory\n\n")
        f.write("HOTKEYS:\n")
        f.write("- Ctrl+Alt+F: Start/Stop recording\n")
        f.write("- Ctrl+Alt+C: Pause/Resume recording\n")
        f.write("- Ctrl+Alt+F6: Load/Unload AI model (VRAM management)\n\n")
        f.write("For more information, visit: https://github.com/your-repo/instant-scribe\n")
    
    print(f"✓ Portable README created: {readme_path}")


def main() -> None:
    """Main entry point for the portable build script."""
    args = parse_args()
    
    print("Building Instant Scribe Portable Distribution")
    print("=" * 45)
    
    try:
        # Verify PyInstaller build exists
        verify_pyinstaller_build(args.source_dir)
        
        # Create output directory
        args.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create temporary directory for building
        temp_dir = args.output_dir / "temp_portable"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        # Build portable structure
        create_portable_structure(args.source_dir, temp_dir)
        
        # Create ZIP file
        zip_path = args.output_dir / args.zip_name
        create_portable_zip(temp_dir, zip_path)
        
        # Create README
        create_portable_readme(args.output_dir)
        
        # Clean up temporary directory
        shutil.rmtree(temp_dir)
        
        print("\n" + "=" * 45)
        print("✓ Portable distribution build completed successfully!")
        print(f"✓ Output: {zip_path}")
        print(f"✓ Size: {zip_path.stat().st_size / (1024 * 1024):.1f} MB")
        print("\nThe portable distribution is ready for distribution.")
        
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
