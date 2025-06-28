# PowerShell Dump Decoder - Task 55.2
# Converts Python crash dumps to human-readable stack traces
#
# Usage:
#   .\dump_decoder.ps1 -DumpFile "path\to\crash_dump.dmp"
#   .\dump_decoder.ps1 -DumpDirectory "path\to\minidumps" -OutputDirectory "path\to\output"
#   .\dump_decoder.ps1 -DumpFile "crash_dump.dmp" -Verbose
#
# Examples:
#   # Decode a single dump file
#   .\dump_decoder.ps1 -DumpFile "logs\minidumps\crash_dump_20250626_120000.dmp"
#
#   # Batch process all dumps in a directory
#   .\dump_decoder.ps1 -DumpDirectory "logs\minidumps" -OutputDirectory "decoded_dumps"
#
#   # Decode with verbose output
#   .\dump_decoder.ps1 -DumpFile "crash_dump.dmp" -Verbose -ShowRawDump

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false, HelpMessage="Path to a single dump file to decode")]
    [string]$DumpFile,
    
    [Parameter(Mandatory=$false, HelpMessage="Directory containing dump files to batch process")]
    [string]$DumpDirectory,
    
    [Parameter(Mandatory=$false, HelpMessage="Output directory for decoded files")]
    [string]$OutputDirectory = "decoded_dumps",
    
    [Parameter(Mandatory=$false, HelpMessage="Show verbose output")]
    [switch]$VerboseOutput,
    
    [Parameter(Mandatory=$false, HelpMessage="Show raw dump content")]
    [switch]$ShowRawDump,
    
    [Parameter(Mandatory=$false, HelpMessage="Output format: Text, JSON, or Both")]
    [ValidateSet("Text", "JSON", "Both")]
    [string]$OutputFormat = "Text"
)

# Set verbose preference
if ($VerboseOutput) {
    $VerbosePreference = "Continue"
}

function Write-Header {
    param([string]$Title)
    
    Write-Host ""
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Yellow
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section {
    param([string]$Title)
    
    Write-Host ""
    Write-Host "-" * 40 -ForegroundColor Green
    Write-Host $Title -ForegroundColor White
    Write-Host "-" * 40 -ForegroundColor Green
}

function Test-PythonAvailable {
    try {
        $pythonVersion = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Verbose "Python available: $pythonVersion"
            return $true
        }
    }
    catch {
        Write-Verbose "Python not found in PATH"
    }
    return $false
}

function Get-DumpMetadata {
    param([string]$DumpPath)
    
    $file = Get-Item $DumpPath -ErrorAction SilentlyContinue
    if (-not $file) {
        return $null
    }
    
    return @{
        Name = $file.Name
        FullPath = $file.FullName
        Size = $file.Length
        Created = $file.CreationTime
        Modified = $file.LastWriteTime
        SizeFormatted = "{0:N2} KB" -f ($file.Length / 1KB)
    }
}

function Read-PythonDumpFile {
    param([string]$DumpPath)
    
    Write-Verbose "Reading dump file: $DumpPath"
    
    try {
        # Python faulthandler dumps are text files, not binary minidumps
        $content = Get-Content -Path $DumpPath -Raw -Encoding UTF8
        
        if ([string]::IsNullOrWhiteSpace($content)) {
            Write-Warning "Dump file is empty or unreadable: $DumpPath"
            return $null
        }
        
        return $content
    }
    catch {
        Write-Error "Failed to read dump file: $_"
        return $null
    }
}

function Parse-PythonStackTrace {
    param([string]$DumpContent)
    
    Write-Verbose "Parsing Python stack trace"
    
    $lines = $DumpContent -split "`n"
    $threads = @()
    $currentThread = $null
    $currentStack = @()
    
    foreach ($line in $lines) {
        $line = $line.Trim()
        
        if ($line -match "^Thread 0x([0-9a-fA-F]+) \(most recent call first\):$") {
            # Save previous thread if exists
            if ($currentThread) {
                $currentThread.StackTrace = $currentStack
                $threads += $currentThread
            }
            
            # Start new thread
            $currentThread = @{
                ThreadId = $matches[1]
                StackTrace = @()
            }
            $currentStack = @()
        }
        elseif ($line -match "^Thread 0x([0-9a-fA-F]+):$") {
            # Save previous thread if exists
            if ($currentThread) {
                $currentThread.StackTrace = $currentStack
                $threads += $currentThread
            }
            
            # Start new thread
            $currentThread = @{
                ThreadId = $matches[1]
                StackTrace = @()
            }
            $currentStack = @()
        }
        elseif ($line -match '^\s+File "([^"]+)", line (\d+), in (.+)$') {
            # Stack frame
            $frame = @{
                File = $matches[1]
                Line = [int]$matches[2]
                Function = $matches[3]
                Code = ""
            }
            $currentStack += $frame
        }
        elseif ($line -match '^\s+(.+)$' -and $currentStack.Count -gt 0) {
            # Code line for the last frame
            $currentStack[-1].Code = $matches[1]
        }
    }
    
    # Save last thread
    if ($currentThread) {
        $currentThread.StackTrace = $currentStack
        $threads += $currentThread
    }
    
    return $threads
}

function Format-StackTraceText {
    param([array]$Threads, [string]$DumpPath)
    
    $metadata = Get-DumpMetadata -DumpPath $DumpPath
    $output = @()
    
    $output += "INSTANT SCRIBE CRASH DUMP ANALYSIS"
    $output += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $output += "Source: $($metadata.FullPath)"
    $output += "Dump Size: $($metadata.SizeFormatted)"
    $output += "Dump Created: $($metadata.Created)"
    $output += ""
    
    $output += "SUMMARY"
    $output += "-------"
    $output += "Total Threads: $($Threads.Count)"
    $output += ""
    
    for ($i = 0; $i -lt $Threads.Count; $i++) {
        $thread = $Threads[$i]
        
        if ($i -eq 0) {
            $output += "MAIN THREAD (0x$($thread.ThreadId)) - Most Recent Call First"
        } else {
            $output += "THREAD $($i + 1) (0x$($thread.ThreadId))"
        }
        $output += "=" * 60
        
        if ($thread.StackTrace.Count -eq 0) {
            $output += "  No stack trace available"
        } else {
            for ($j = 0; $j -lt $thread.StackTrace.Count; $j++) {
                $frame = $thread.StackTrace[$j]
                $output += "  Frame $($j + 1):"
                $output += "    File: $($frame.File)"
                $output += "    Line: $($frame.Line)"
                $output += "    Function: $($frame.Function)"
                if ($frame.Code) {
                    $output += "    Code: $($frame.Code)"
                }
                $output += ""
            }
        }
        $output += ""
    }
    
    return $output -join "`n"
}

function Format-StackTraceJSON {
    param([array]$Threads, [string]$DumpPath)
    
    $metadata = Get-DumpMetadata -DumpPath $DumpPath
    
    $result = @{
        analysis_info = @{
            generated = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
            source_file = $metadata.FullPath
            dump_size_bytes = $metadata.Size
            dump_created = $metadata.Created.ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
        summary = @{
            total_threads = $Threads.Count
        }
        threads = @()
    }
    
    for ($i = 0; $i -lt $Threads.Count; $i++) {
        $thread = $Threads[$i]
        
        $threadInfo = @{
            thread_number = $i + 1
            thread_id = "0x$($thread.ThreadId)"
            is_main_thread = ($i -eq 0)
            stack_frames = @()
        }
        
        for ($j = 0; $j -lt $thread.StackTrace.Count; $j++) {
            $frame = $thread.StackTrace[$j]
            $frameInfo = @{
                frame_number = $j + 1
                file = $frame.File
                line = $frame.Line
                function = $frame.Function
                code = $frame.Code
            }
            $threadInfo.stack_frames += $frameInfo
        }
        
        $result.threads += $threadInfo
    }
    
    return $result | ConvertTo-Json -Depth 10
}

function Process-DumpFile {
    param([string]$DumpPath, [string]$OutputDir)
    
    Write-Header "Processing Dump File: $(Split-Path $DumpPath -Leaf)"
    
    # Read and parse dump
    $dumpContent = Read-PythonDumpFile -DumpPath $DumpPath
    if (-not $dumpContent) {
        Write-Error "Failed to read dump file: $DumpPath"
        return
    }
    
    if ($ShowRawDump) {
        Write-Section "Raw Dump Content"
        Write-Host $dumpContent -ForegroundColor Gray
    }
    
    $threads = Parse-PythonStackTrace -DumpContent $dumpContent
    
    if ($threads.Count -eq 0) {
        Write-Warning "No threads found in dump file"
        return
    }
    
    Write-Section "Analysis Results"
    Write-Host "Found $($threads.Count) thread(s)" -ForegroundColor Green
    
    # Generate output filename
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($DumpPath)
    
    # Create output directory
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
        Write-Verbose "Created output directory: $OutputDir"
    }
    
    # Generate outputs based on format
    if ($OutputFormat -eq "Text" -or $OutputFormat -eq "Both") {
        $textOutput = Format-StackTraceText -Threads $threads -DumpPath $DumpPath
        $textFile = Join-Path $OutputDir "$baseName.txt"
        $textOutput | Out-File -FilePath $textFile -Encoding UTF8
        Write-Host "Text analysis saved to: $textFile" -ForegroundColor Cyan
        
        # Also display to console
        Write-Section "Stack Trace Analysis"
        Write-Host $textOutput
    }
    
    if ($OutputFormat -eq "JSON" -or $OutputFormat -eq "Both") {
        $jsonOutput = Format-StackTraceJSON -Threads $threads -DumpPath $DumpPath
        $jsonFile = Join-Path $OutputDir "$baseName.json"
        $jsonOutput | Out-File -FilePath $jsonFile -Encoding UTF8
        Write-Host "JSON analysis saved to: $jsonFile" -ForegroundColor Cyan
    }
}

function Main {
    Write-Header "Instant Scribe Dump Decoder"
    Write-Host "PowerShell tool for converting Python crash dumps to human-readable stack traces" -ForegroundColor Gray
    
    # Validate parameters
    if (-not $DumpFile -and -not $DumpDirectory) {
        Write-Error "Either -DumpFile or -DumpDirectory must be specified"
        Write-Host ""
        Write-Host "Usage examples:"
        Write-Host "  .\dump_decoder.ps1 -DumpFile 'crash_dump.dmp'"
        Write-Host "  .\dump_decoder.ps1 -DumpDirectory 'logs\minidumps'"
        return
    }
    
    if ($DumpFile -and $DumpDirectory) {
        Write-Error "Cannot specify both -DumpFile and -DumpDirectory"
        return
    }
    
    # Process single file
    if ($DumpFile) {
        if (-not (Test-Path $DumpFile)) {
            Write-Error "Dump file not found: $DumpFile"
            return
        }
        
        Process-DumpFile -DumpPath $DumpFile -OutputDir $OutputDirectory
    }
    
    # Process directory
    if ($DumpDirectory) {
        if (-not (Test-Path $DumpDirectory)) {
            Write-Error "Dump directory not found: $DumpDirectory"
            return
        }
        
        $dumpFiles = Get-ChildItem -Path $DumpDirectory -Filter "*.dmp" -File
        
        if ($dumpFiles.Count -eq 0) {
            Write-Warning "No .dmp files found in directory: $DumpDirectory"
            return
        }
        
        Write-Host "Found $($dumpFiles.Count) dump file(s) to process" -ForegroundColor Green
        
        foreach ($file in $dumpFiles) {
            Process-DumpFile -DumpPath $file.FullName -OutputDir $OutputDirectory
            Write-Host ""
        }
    }
    
    Write-Header "Processing Complete"
    Write-Host "Output directory: $OutputDirectory" -ForegroundColor Green
}

# Run main function
Main
