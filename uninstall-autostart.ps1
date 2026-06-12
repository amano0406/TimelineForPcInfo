[CmdletBinding()]
param(
    [string]$TaskName = "TimelineForPcInfo Local API",
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StopScript = Join-Path $ProductRoot "stop.ps1"
$WatchdogPidFile = Join-Path $ProductRoot ".runtime\watchdog.pid"
$StartupDir = [Environment]::GetFolderPath("Startup")
$StartupLauncher = if ($StartupDir) { Join-Path $StartupDir "TimelineForPcInfo Local API.cmd" } else { $null }

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

function Test-TimelineForPcInfoWatchdogCommandLine {
    param([string]$CommandLine)

    if (-not $CommandLine) {
        return $false
    }

    $escapedProductRoot = [regex]::Escape($ProductRoot)
    return (($CommandLine -match "watchdog\.ps1") -and ($CommandLine -match $escapedProductRoot))
}

function Stop-TimelineForPcInfoWatchdog {
    if (-not (Test-Path -LiteralPath $WatchdogPidFile)) {
        return
    }

    $pidText = (Get-Content -LiteralPath $WatchdogPidFile -Raw).Trim()
    $processId = 0
    if (-not [int]::TryParse($pidText, [ref]$processId)) {
        Remove-Item -LiteralPath $WatchdogPidFile -Force
        return
    }

    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $WatchdogPidFile -Force
        return
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

    if ($commandLine -and (-not (Test-TimelineForPcInfoWatchdogCommandLine -CommandLine $commandLine))) {
        throw "Refusing to stop process $processId because it does not look like TimelineForPcInfo watchdog."
    }

    Stop-TimelineForPcInfoProcessTree -RootProcessId $processId
    Remove-Item -LiteralPath $WatchdogPidFile -Force
    Write-Host "TimelineForPcInfo watchdog stopped. pid=$processId"
}

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $Task) {
    Write-Host "TimelineForPcInfo autostart task is not installed. task=$TaskName"
}
else {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "TimelineForPcInfo autostart task removed. task=$TaskName"
}

if ($StartupLauncher -and (Test-Path -LiteralPath $StartupLauncher)) {
    Remove-Item -LiteralPath $StartupLauncher -Force
    Write-Host "TimelineForPcInfo Startup launcher removed. path=$StartupLauncher"
}

Stop-TimelineForPcInfoWatchdog

if ($Stop) {
    if (-not (Test-Path -LiteralPath $StopScript -PathType Leaf)) {
        throw "TimelineForPcInfo stop script was not found: $StopScript"
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript
    exit $LASTEXITCODE
}
