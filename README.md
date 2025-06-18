# Instant-Scribe

## Development Environment Setup

The project uses a dedicated Python virtual environment to isolate dependencies. Follow these steps to get up and running on Windows 10 (PowerShell):

```powershell
# 1. Clone the repository and cd into it
# git clone https://github.com/<your-fork>/Instant-Scribe.git
# cd Instant-Scribe

# 2. Create a Python 3.10 (or newer) virtual environment in .venv
python -m venv .venv

# 3. Activate the environment for the current session
.\.venv\Scripts\activate

# 4. Upgrade pip and install project requirements
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 5. Verify that the environment is working
python -m pip list
```

A convenience bootstrap script is available under `scripts/setup_env.ps1` that automates steps 2-4.

### Regenerating the lock-file (requirements.txt)

High-level dependencies live in `requirements.in`. Run the following **inside the activated venv** whenever you add or update a dependency:

```powershell
pip install pip-tools
pip-compile --upgrade --output-file requirements.txt requirements.in
```

## NVIDIA Parakeet Model

Instant Scribe relies exclusively on the **NVIDIA Parakeet TDT 0.6B-v2** speech-to-text model. The model is pulled on first run by the NeMo toolkit and cached locally (see `transcription_worker.py`).

### Verify CUDA visibility

Run the simple smoke-test to confirm PyTorch detects your NVIDIA GPU:

```powershell
python scripts/check_cuda.py
```

You should see output similar to:

```
✅ CUDA is available!
   • Device index : 0
   • Name         : NVIDIA GeForce RTX 4070
   • Total VRAM   : 8.00 GB
   • Compute (SM) : 8.9
   • PyTorch CUDA : 12.1
```

If you receive an error, install/upgrade your GPU driver and ensure you used the CUDA-enabled PyTorch wheel.