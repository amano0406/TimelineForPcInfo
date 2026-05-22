[CmdletBinding()]
param(
    [string]$TaskName = "TimelineForPC Local API",
    [int]$KeepAliveMinutes = 5,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $ProductRoot "start.ps1"
$WatchdogScript = Join-Path $ProductRoot "watchdog.ps1"

if (-not (Test-Path -LiteralPath $StartScript -PathType Leaf)) {
    throw "TimelineForPC start script was not found: $StartScript"
}

if (-not (Test-Path -LiteralPath $WatchdogScript -PathType Leaf)) {
    throw "TimelineForPC watchdog script was not found: $WatchdogScript"
}

if ($KeepAliveMinutes -lt 1 -or $KeepAliveMinutes -gt 1440) {
    throw "KeepAliveMinutes must be between 1 and 1440."
}

$WatchdogIntervalSeconds = $KeepAliveMinutes * 60
$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$ActionArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`""
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $ActionArgs -WorkingDirectory $ProductRoot

$Triggers = @(
    New-ScheduledTaskTrigger -AtLogOn
)
$Triggers += New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $KeepAliveMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$Description = "Keeps the TimelineForPC local API running for the current Windows user."

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Triggers `
        -Settings $Settings `
        -Description $Description `
        -Force | Out-Null
    Write-Host "TimelineForPC autostart installed. mode=scheduled_task task=$TaskName keepAliveMinutes=$KeepAliveMinutes"

    if (-not $NoStart) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript
        exit $LASTEXITCODE
    }

    exit 0
}
catch {
    Write-Warning "Scheduled Task registration failed. Falling back to current-user Startup watchdog. $($_.Exception.Message)"
}

$StartupDir = [Environment]::GetFolderPath("Startup")
if (-not $StartupDir) {
    throw "Current-user Startup folder was not found."
}

New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null
$StartupLauncher = Join-Path $StartupDir "TimelineForPC Local API.cmd"
$LauncherContent = @(
    "@echo off",
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WatchdogScript`" -IntervalSeconds $WatchdogIntervalSeconds"
)
Set-Content -LiteralPath $StartupLauncher -Value $LauncherContent -Encoding ASCII
Write-Host "TimelineForPC autostart installed. mode=startup_watchdog launcher=$StartupLauncher keepAliveMinutes=$KeepAliveMinutes"

if (-not $NoStart) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $WatchdogScript -IntervalSeconds $WatchdogIntervalSeconds
    exit $LASTEXITCODE
}
