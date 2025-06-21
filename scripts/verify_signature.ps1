param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Path
)

if (-not (Test-Path -Path $Path -PathType Leaf)) {
    Write-Error "File not found: $Path"
    exit 1
}

try {
    $sig = Get-AuthenticodeSignature -FilePath $Path -ErrorAction Stop
} catch {
    Write-Error "Get-AuthenticodeSignature failed: $_"
    exit 1
}

switch ($sig.Status) {
    'Valid' {
        Write-Host "Signature valid." -ForegroundColor Green
        exit 0
    }
    default {
        Write-Error "Signature check failed: $($sig.Status)"
        exit 1
    }
} 