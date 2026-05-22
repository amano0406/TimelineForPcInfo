[CmdletBinding()]
param(
    [string]$TaskName = "TimelineForPC Local API",
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StopScript = Join-Path $ProductRoot "stop.ps1"
$WatchdogPidFile = Join-Path $ProductRoot ".runtime\watchdog.pid"
$StartupDir = [Environment]::GetFolderPath("Startup")
$StartupLauncher = if ($StartupDir) { Join-Path $StartupDir "TimelineForPC Local API.cmd" } else { $null }

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

function Test-TimelineForPcWatchdogCommandLine {
    param([string]$CommandLine)

    if (-not $CommandLine) {
        return $false
    }

    $escapedProductRoot = [regex]::Escape($ProductRoot)
    return (($CommandLine -match "watchdog\.ps1") -and ($CommandLine -match $escapedProductRoot))
}

function Stop-TimelineForPcWatchdog {
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

    if ($commandLine -and (-not (Test-TimelineForPcWatchdogCommandLine -CommandLine $commandLine))) {
        throw "Refusing to stop process $processId because it does not look like TimelineForPC watchdog."
    }

    Stop-TimelineForPcProcessTree -RootProcessId $processId
    Remove-Item -LiteralPath $WatchdogPidFile -Force
    Write-Host "TimelineForPC watchdog stopped. pid=$processId"
}

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $Task) {
    Write-Host "TimelineForPC autostart task is not installed. task=$TaskName"
}
else {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "TimelineForPC autostart task removed. task=$TaskName"
}

if ($StartupLauncher -and (Test-Path -LiteralPath $StartupLauncher)) {
    Remove-Item -LiteralPath $StartupLauncher -Force
    Write-Host "TimelineForPC Startup launcher removed. path=$StartupLauncher"
}

Stop-TimelineForPcWatchdog

if ($Stop) {
    if (-not (Test-Path -LiteralPath $StopScript -PathType Leaf)) {
        throw "TimelineForPC stop script was not found: $StopScript"
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript
    exit $LASTEXITCODE
}
