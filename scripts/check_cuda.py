"""Smoke-test script to verify that PyTorch can access a CUDA-capable GPU.

Usage:
    python scripts/check_cuda.py

Exit status:
    0 – CUDA is available and ready.
    1 – CUDA not available or driver mismatch.
"""
from __future__ import annotations

import sys
import textwrap

try:
    import torch
except ImportError as exc:
    sys.exit("ERROR: PyTorch is not installed (import failed). Install requirements first.")

if not torch.cuda.is_available():
    sys.exit("ERROR: CUDA is NOT available. Verify NVIDIA drivers, CUDA toolkit, and that you installed the correct PyTorch build.")

idx = torch.cuda.current_device()
props = torch.cuda.get_device_properties(idx)
print(textwrap.dedent(
    f"""
    CUDA is available!
       • Device index : {idx}
       • Name         : {props.name}
       • Total VRAM   : {props.total_memory / 1e9:.2f} GB
       • Compute (SM) : {props.major}.{props.minor}
       • PyTorch CUDA : {torch.version.cuda}
    """
))

REQUIRED_PY_VERSION = (3, 10)
if sys.version_info[:2] != REQUIRED_PY_VERSION:
    sys.exit(
        f"ERROR: Python {REQUIRED_PY_VERSION[0]}.{REQUIRED_PY_VERSION[1]} is required, but you are running {sys.version.split()[0]}."
    )

print(f"Python version {sys.version.split()[0]} OK.")

try:
    import nemo.collections.asr as _  # noqa: F401
except ImportError:
    sys.exit("ERROR: NVIDIA NeMo ASR collection is not installed. Ensure nemo_toolkit[asr] is present in requirements.")

print("NeMo toolkit import OK.")

sys.exit(0) 