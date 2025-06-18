<#
    setup_env.ps1 - Bootstrap script for Instant Scribe dev environment.

    Usage (run from repo root):
        ./scripts/setup_env.ps1 [-PythonExe python3.10] [-SkipInstall]

    - Creates a local virtual environment at .venv
    - Upgrades pip
    - Installs dependencies from requirements.txt (unless -SkipInstall is supplied)
#>

param(
    [string]$PythonExe = "python",
    [switch]$SkipInstall
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

    Write-Host "[Instant Scribe] Installing dependencies from requirements.txt..." -ForegroundColor Cyan
    python -m pip install -r requirements.txt
}

Write-Host "[Instant Scribe] Environment setup complete!`n`nTo activate in future sessions run:`n  .\.venv\Scripts\activate" -ForegroundColor Green 