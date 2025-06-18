# Instant Scribe - Environment Setup Script
#
# This script prepares the development environment for the Instant Scribe project.
# It ensures the correct Python version is used and creates an isolated virtual environment.

$ErrorActionPreference = 'Stop'
$requiredPythonVersion = [version]"3.10"
$venvDir = ".venv"

# 1. Verify Python Version
Write-Host "Verifying Python version..."
try {
    $pythonVersionString = (python --version) -replace "Python ", ""
    $pythonVersion = [version]$pythonVersionString
    Write-Host "Found Python version $pythonVersion."
} catch {
    Write-Error "Python not found. Please install Python $($requiredPythonVersion.Major).$($requiredPythonVersion.Minor) or newer and ensure it's in your PATH."
    exit 1
}

if ($pythonVersion -lt $requiredPythonVersion) {
    Write-Error "Python version $requiredPythonVersion or higher is required. You have $pythonVersion."
    exit 1
}

# 2. Create Virtual Environment
if (Test-Path -Path $venvDir) {
    Write-Warning "Virtual environment '$venvDir' already exists. Skipping creation."
} else {
    Write-Host "Creating Python virtual environment in '$venvDir'..."
    python -m venv $venvDir
    Write-Host "Virtual environment created successfully."
}

# 3. Provide Activation Instructions
Write-Host "
Setup complete.

To activate the virtual environment, run the following command in your PowerShell terminal:
`./.venv/Scripts/Activate.ps1`

Once activated, you can install dependencies using:
`pip install -r requirements.txt`
" 