[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ProductRoot ".runtime\health.pid"

function Stop-TimelineForPcProcessTree {
    param([int]$RootProcessId)

    if ($RootProcessId -le 0) {
        return
    }

    $pending = @([int]$RootProcessId)
    $processIds = @()
    $seen = @{}
    while ($pending.Count -gt 0) {
        $current = [int]$pending[0]
        if ($pending.Count -eq 1) {
            $pending = @()
        }
        else {
            $pending = @($pending[1..($pending.Count - 1)])
        }

        $key = [string]$current
        if ($seen.ContainsKey($key)) {
            continue
        }
        $seen[$key] = $true
        $processIds += $current

        try {
            $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $current" -ErrorAction Stop)
            foreach ($child in $children) {
                $pending += [int]$child.ProcessId
            }
        }
        catch {
        }
    }

    for ($index = $processIds.Count - 1; $index -ge 0; $index--) {
        try {
            Stop-Process -Id ([int]$processIds[$index]) -Force -ErrorAction Stop
        }
        catch {
        }
    }
}

function Test-TimelineForPcApiCommandLine {
    param([string]$CommandLine)

    if (-not $CommandLine) {
        return $false
    }

    $escapedProductRoot = [regex]::Escape($ProductRoot)
    return ($CommandLine -match "timeline_for_pc\.api_server" -and $CommandLine -match $escapedProductRoot)
}

function Test-TimelineForPcApiModuleCommandLine {
    param([string]$CommandLine)

    if (-not $CommandLine) {
        return $false
    }

    return (
        ($CommandLine -match "timeline_for_pc\.api_server") -or
        (($CommandLine -match "TimelineForPC\.Api\.exe") -and ($CommandLine -match [regex]::Escape($ProductRoot)))
    )
}

function Stop-TimelineForPcApiModuleProcesses {
    try {
        $matches = @(
            Get-CimInstance Win32_Process -ErrorAction Stop |
                Where-Object { Test-TimelineForPcApiModuleCommandLine -CommandLine ([string]$_.CommandLine) }
        )
    }
    catch {
        $matches = @()
    }

    foreach ($match in $matches) {
        Stop-TimelineForPcProcessTree -RootProcessId ([int]$match.ProcessId)
    }
}

if (-not (Test-Path -LiteralPath $PidFile)) {
    Stop-TimelineForPcApiModuleProcesses
    Write-Host "TimelineForPC health API is not running."
    exit 0
}

$pidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
$processId = 0
if (-not [int]::TryParse($pidText, [ref]$processId)) {
    Remove-Item -LiteralPath $PidFile -Force
    Stop-TimelineForPcApiModuleProcesses
    Write-Host "TimelineForPC health API pid file was invalid and has been removed."
    exit 0
}

$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($null -eq $process) {
    Remove-Item -LiteralPath $PidFile -Force
    Stop-TimelineForPcApiModuleProcesses
    Write-Host "TimelineForPC health API was not running."
    exit 0
}

$commandLine = ""
try {
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
    if ($null -ne $cim) {
        $commandLine = [string]$cim.CommandLine
    }
}
catch {
    $commandLine = ""
}

if ($commandLine -and (-not (Test-TimelineForPcApiCommandLine -CommandLine $commandLine)) -and (-not (Test-TimelineForPcApiModuleCommandLine -CommandLine $commandLine))) {
    throw "Refusing to stop process $processId because it does not look like TimelineForPC local API."
}

Stop-TimelineForPcProcessTree -RootProcessId $processId
Remove-Item -LiteralPath $PidFile -Force
Write-Host "TimelineForPC local API stopped. pid=$processId"
