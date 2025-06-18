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
sys.exit(0) 