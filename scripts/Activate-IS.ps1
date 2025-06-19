# Activate-IS.ps1 — lightweight PowerShell activator for the Instant Scribe dev virtual-env
# -----------------------------------------------------------------------------
# Dot-source this file to activate the .venv **without** modifying the venv
# directory in any way (respects the preserve_venv rule).
#
#    PS> . ./scripts/Activate-IS.ps1
#
# Once active you can leave the environment with the usual `deactivate` command
# (defined below).

param(
    [string]$VenvPath = "$(Join-Path $PSScriptRoot '..\.venv')"
)

$venv = Resolve-Path $VenvPath -ErrorAction Stop

# Cache originals so that we can cleanly undo the changes in `deactivate`.
$env:_OLD_VIRTUAL_PATH = $env:PATH
$env:VIRTUAL_ENV         = $venv
$env:PATH                = "$env:VIRTUAL_ENV\Scripts;" + $env:_OLD_VIRTUAL_PATH

# Persist the existing prompt for later restoration
if (-not (Test-Path Function:\prompt)) {
    function global:prompt { "PS> " }
}
$function:__origPrompt = (Get-Command prompt).ScriptBlock

function global:deactivate {
    Remove-Item Function:\global:deactivate -ErrorAction SilentlyContinue
    $env:PATH = $env:_OLD_VIRTUAL_PATH
    Remove-Item Env:_OLD_VIRTUAL_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:VIRTUAL_ENV      -ErrorAction SilentlyContinue
    function global:prompt { & $function:__origPrompt }
}

function global:prompt {
    "(InstantScribe) " + (& $function:__origPrompt)
}

Write-Host "[Instant Scribe] .venv activated — type 'deactivate' to leave." -ForegroundColor Green 