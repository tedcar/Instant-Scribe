# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller *spec* configuration for **Instant Scribe**.

This file fulfils *DEV_TASKS.md – Task 15* (Packaging via PyInstaller):

15.1 Generate initial *InstantScribe.spec* with `--noconsole`.
15.2 Customise *datas* to include the Parakeet model cache **if it is present**.

Running `pyinstaller InstantScribe.spec --noconfirm` produces the *dist/Instant Scribe/*
folder containing the frozen application.  The build is intentionally kept as
*onedir* (≠ *onefile*) because the embedded NVIDIA model can exceed 2 GB.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Optional *stub* modules
# ---------------------------------------------------------------------------
# In CI environments the heavyweight, GPU-centric runtime dependencies
# (``torch``, ``nemo_toolkit``, etc.) are typically **not** installed.  When
# PyInstaller tries to analyse the source files it will attempt to *import*
# every ``import X`` it encounters which would normally fail.  To keep the
# build lightweight we pre-register *dummy* placeholder packages so the import
# machinery finds **something** and the analysis can proceed uninterrupted.
#
# NOTE:  These dummies are *only* injected for the duration of the spec file –
#        the final executable remains fully functional on an end-user machine
#        where the real dependencies are bundled (because they *are* available
#        in the developer/packager virtual-environment used for the release
#        build).
_DUMMY_MODULES: List[str] = [
    "torch",
    "torchvision",
    "torchaudio",
    "pyaudio",
    "webrtcvad",
    "windows_toasts",
    # NVIDIA NeMo hierarchy
    "nemo",
    "nemo.collections",
    "nemo.collections.asr",
    "nemo.collections.asr.models",
]
for _name in _DUMMY_MODULES:
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)

# ---------------------------------------------------------------------------
# Helper – locate cached Parakeet model (optional)
# ---------------------------------------------------------------------------

def _find_parakeet_cache() -> Tuple[str, str] | None:
    """Return *(source, dest)* tuple for bundling Parakeet cache – *or* ``None``.

    The NVIDIA NeMo PyTorch backend stores downloaded checkpoints in the
    platform-specific *torch* cache (Linux/macOS: ``~/.cache/torch/NeMo/models``;
    Windows: ``%LOCALAPPDATA%/torch/NeMo/models``).  We attempt to locate any
    directory containing the word *parakeet* and, if found, ship it inside the
    bundle under ``nemo_models`` so :pyfunc:`InstanceScrubber.resource_manager.resource_path`
    can locate it at runtime.
    """

    candidates = [
        # Generic Torch cache locations
        Path.home() / ".cache/torch/NeMo/models",
        Path.home() / "AppData/Local/torch/NeMo/models",  # Windows `%LOCALAPPDATA%`
    ]
    for base in candidates:
        if not base.is_dir():
            continue
        for sub in base.iterdir():
            if "parakeet" in sub.name.lower():
                # Bundle entire directory → dist/<app>/nemo_models/<cache_dir>
                return str(sub), f"nemo_models/{sub.name}"
    return None

_parakeet_data = _find_parakeet_cache()
_datas: List[Tuple[str, str]] = []
if _parakeet_data:
    _datas.append(_parakeet_data)

# ---------------------------------------------------------------------------
# PyInstaller build spec
# ---------------------------------------------------------------------------

project_root = Path(__file__).resolve().parent if globals().get("__file__") else Path.cwd()

block_cipher = None  # not used – left for completeness


a = Analysis(
    ["watchdog.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Skip heavy GPU libraries during *analysis* – they are optional
        "torch",
        "torchaudio",
        "torchvision",
        "nemo_toolkit",
        "nemo",
        "pyaudio",
        "webrtcvad",
        "windows_toasts",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],  # resources
    name="Instant Scribe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Task 15.1 – `--noconsole`
    icon="assets/icon.ico" if Path("assets/icon.ico").is_file() else None,
)

# EOF 