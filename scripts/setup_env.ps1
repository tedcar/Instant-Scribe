<#
    setup_env.ps1 - Bootstrap script for Instant Scribe dev environment.

    Usage (run from repo root):
        ./scripts/setup_env.ps1 [-PythonExe python3.10] [-SkipInstall]

    - Creates a local virtual environment at .venv
    - Upgrades pip
    - Installs dependencies from requirements.txt (unless -SkipInstall is supplied)
#>

param(
    [string]$PythonExe = "python3.10",
    [switch]$SkipInstall,
    [string]$CudaVersion = "cu118"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[Instant Scribe] Creating virtual environment (.venv)..." -ForegroundColor Cyan
& $PythonExe -m venv .venv

Write-Host "[Instant Scribe] Activating virtual environment..." -ForegroundColor Cyan
& .\.venv\Scripts\activate

if (-not $SkipInstall) {
    Write-Host "[Instant Scribe] Upgrading pip..." -ForegroundColor Cyan
    python -m pip install --upgrade pip

    Write-Host "[Instant Scribe] Installing CUDA-enabled PyTorch (GPU build)..." -ForegroundColor Cyan
    $torchVer = "2.3.0+$CudaVersion"
    $indexUrl = "https://download.pytorch.org/whl/$CudaVersion"
    python -m pip install "torch==$torchVer" torchvision torchaudio --index-url $indexUrl

    Write-Host "[Instant Scribe] Installing project Python requirements..." -ForegroundColor Cyan
    python -m pip install -r requirements.txt

    # Ensure system-level audio tools are available
    Write-Host "[Instant Scribe] Verifying system audio dependencies (sox, ffmpeg)..." -ForegroundColor Cyan
    try {
        if (-not (Get-Command sox -ErrorAction SilentlyContinue)) {
            Write-Host "  • sox not found → installing via Chocolatey..." -ForegroundColor Yellow
            choco install -y sox
        }
        if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            Write-Host "  • ffmpeg not found → installing via Chocolatey..." -ForegroundColor Yellow
            choco install -y ffmpeg
        }
    } catch {
        Write-Warning "Chocolatey not found or installation failed. Please install sox & ffmpeg manually and ensure they are on PATH."
    }
}

Write-Host "[Instant Scribe] Environment setup complete!`n`nTo activate in future sessions run:`n  .\.venv\Scripts\activate" -ForegroundColor Green 