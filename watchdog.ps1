[CmdletBinding()]
param(
    [int]$IntervalSeconds = 300,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProductRoot ".runtime"
$PidFile = Join-Path $RuntimeDir "watchdog.pid"
$LogFile = Join-Path $RuntimeDir "watchdog.log"
$StartScript = Join-Path $ProductRoot "start.ps1"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

if (-not (Test-Path -LiteralPath $StartScript -PathType Leaf)) {
    throw "TimelineForPC start script was not found: $StartScript"
}

if ($IntervalSeconds -lt 10 -or $IntervalSeconds -gt 86400) {
    throw "IntervalSeconds must be between 10 and 86400."
}

function Test-TimelineForPcWatchdogCommandLine {
    param([string]$CommandLine)

    if (-not $CommandLine) {
        return $false
    }

    $escapedProductRoot = [regex]::Escape($ProductRoot)
    return (($CommandLine -match "watchdog\.ps1") -and ($CommandLine -match $escapedProductRoot))
}

function Get-TimelineForPcWatchdogProcess {
    try {
        return @(
            Get-CimInstance Win32_Process -ErrorAction Stop |
                Where-Object {
                    ([int]$_.ProcessId -ne [int]$PID) -and
                    (Test-TimelineForPcWatchdogCommandLine -CommandLine ([string]$_.CommandLine))
                } |
                Select-Object -First 1
        )
    }
    catch {
        return @()
    }
}

if (-not $Foreground) {
    if (Test-Path -LiteralPath $PidFile) {
        $existingPidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
        $existingPid = 0
        if ([int]::TryParse($existingPidText, [ref]$existingPid)) {
            $existing = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
            if ($null -ne $existing) {
                $commandLine = ""
                try {
                    $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $existingPid"
                    if ($null -ne $cim) {
                        $commandLine = [string]$cim.CommandLine
                    }
                }
                catch {
                    $commandLine = ""
                }
                if (Test-TimelineForPcWatchdogCommandLine -CommandLine $commandLine) {
                    Write-Host "TimelineForPC watchdog is already running. pid=$existingPid"
                    exit 0
                }
            }
        }
        Remove-Item -LiteralPath $PidFile -Force
    }

    $running = Get-TimelineForPcWatchdogProcess
    if ($running.Count -gt 0) {
        Set-Content -LiteralPath $PidFile -Value ([string]$running[0].ProcessId) -Encoding ASCII
        Write-Host "TimelineForPC watchdog is already running. pid=$($running[0].ProcessId)"
        exit 0
    }

    $watchdogArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $MyInvocation.MyCommand.Path,
        "-Foreground",
        "-IntervalSeconds",
        [string]$IntervalSeconds
    )
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $watchdogArgs -WorkingDirectory $ProductRoot -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath $PidFile -Value ([string]$process.Id) -Encoding ASCII
    Write-Host "TimelineForPC watchdog started. pid=$($process.Id) intervalSeconds=$IntervalSeconds"
    exit 0
}

Set-Content -LiteralPath $PidFile -Value ([string]$PID) -Encoding ASCII

while ($true) {
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript | Out-Null
        Add-Content -LiteralPath $LogFile -Value "$stamp OK"
    }
    catch {
        Add-Content -LiteralPath $LogFile -Value "$stamp NG $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $IntervalSeconds
}
