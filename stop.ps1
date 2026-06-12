[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ProductRoot ".runtime\health.pid"

function Stop-TimelineForPcInfoProcessTree {
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

function Test-TimelineForPcInfoApiCommandLine {
    param([string]$CommandLine)

    if (-not $CommandLine) {
        return $false
    }

    $escapedProductRoot = [regex]::Escape($ProductRoot)
    return ($CommandLine -match "timeline_for_pc_info\.api_server" -and $CommandLine -match $escapedProductRoot)
}

function Test-TimelineForPcInfoApiModuleCommandLine {
    param([string]$CommandLine)

    if (-not $CommandLine) {
        return $false
    }

    return (
        ($CommandLine -match "timeline_for_pc_info\.api_server") -or
        (($CommandLine -match "TimelineForPcInfo\.Api\.exe") -and ($CommandLine -match [regex]::Escape($ProductRoot)))
    )
}

function Stop-TimelineForPcInfoApiModuleProcesses {
    try {
        $matches = @(
            Get-CimInstance Win32_Process -ErrorAction Stop |
                Where-Object { Test-TimelineForPcInfoApiModuleCommandLine -CommandLine ([string]$_.CommandLine) }
        )
    }
    catch {
        $matches = @()
    }

    foreach ($match in $matches) {
        Stop-TimelineForPcInfoProcessTree -RootProcessId ([int]$match.ProcessId)
    }
}

if (-not (Test-Path -LiteralPath $PidFile)) {
    Stop-TimelineForPcInfoApiModuleProcesses
    Write-Host "TimelineForPcInfo health API is not running."
    exit 0
}

$pidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
$processId = 0
if (-not [int]::TryParse($pidText, [ref]$processId)) {
    Remove-Item -LiteralPath $PidFile -Force
    Stop-TimelineForPcInfoApiModuleProcesses
    Write-Host "TimelineForPcInfo health API pid file was invalid and has been removed."
    exit 0
}

$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($null -eq $process) {
    Remove-Item -LiteralPath $PidFile -Force
    Stop-TimelineForPcInfoApiModuleProcesses
    Write-Host "TimelineForPcInfo health API was not running."
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

if ($commandLine -and (-not (Test-TimelineForPcInfoApiCommandLine -CommandLine $commandLine)) -and (-not (Test-TimelineForPcInfoApiModuleCommandLine -CommandLine $commandLine))) {
    throw "Refusing to stop process $processId because it does not look like TimelineForPcInfo local API."
}

Stop-TimelineForPcInfoProcessTree -RootProcessId $processId
Remove-Item -LiteralPath $PidFile -Force
Write-Host "TimelineForPcInfo local API stopped. pid=$processId"
