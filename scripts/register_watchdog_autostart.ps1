# PowerShell script to register Instant Scribe watchdog for autostart on Windows login.
#
# Usage (elevated prompt recommended):
#   .\register_watchdog_autostart.ps1
#
# The script creates a shortcut in the current user's *Startup* folder that
# launches *watchdog.py* via *pythonw.exe* (GUI-less interpreter).  Existing
# shortcuts with the same name are overwritten.

param(
    [string]$WatchdogScriptPath = (Resolve-Path -Path (Join-Path -Path $PSScriptRoot -ChildPath "..\watchdog.py")).Path
)

Write-Host "Registering Instant Scribe watchdog autostart…"

$pythonw = Join-Path -Path ([System.IO.Path]::GetDirectoryName($(Get-Command python).Source)) -ChildPath "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Warning "pythonw.exe not found next to python – falling back to python.exe hidden window";
    $pythonw = $(Get-Command python).Source
}

# Compose shortcut properties
$startupDir = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path -Path $startupDir -ChildPath 'Instant Scribe.lnk'
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "`"$WatchdogScriptPath`""
$shortcut.WorkingDirectory = Split-Path -Path $WatchdogScriptPath -Parent
$shortcut.WindowStyle = 7  # Minimized
$shortcut.IconLocation = ''
$shortcut.Save()

Write-Host "Shortcut created at $shortcutPath" 