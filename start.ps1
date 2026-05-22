[CmdletBinding()]
param(
    [int]$Port = 0,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProductRoot ".runtime"
$PidFile = Join-Path $RuntimeDir "health.pid"
$SourceRoot = Join-Path $ProductRoot "src"
$ApiModulePath = Join-Path $SourceRoot "timeline_for_pc\api_server.py"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

function Test-TimelineForPcApiCommandLine {
    param([string]$CommandLine)

    if (-not $CommandLine) {
        return $false
    }

    $escapedProductRoot = [regex]::Escape($ProductRoot)
    return (
        ($CommandLine -match "timeline_for_pc\.api_server") -and
        ($CommandLine -match $escapedProductRoot)
    )
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

function Get-TimelineForPcApiProcess {
    try {
        $matches = @(
            Get-CimInstance Win32_Process -ErrorAction Stop |
                Where-Object { Test-TimelineForPcApiCommandLine -CommandLine ([string]$_.CommandLine) }
        )
    }
    catch {
        return $null
    }

    if ($matches.Count -eq 0) {
        return $null
    }

    return ($matches | Select-Object -First 1)
}

function Get-TimelineForPcApiModuleProcesses {
    try {
        return @(
            Get-CimInstance Win32_Process -ErrorAction Stop |
                Where-Object { Test-TimelineForPcApiModuleCommandLine -CommandLine ([string]$_.CommandLine) }
        )
    }
    catch {
        return @()
    }
}

function Test-TimelineForPcApiHealth {
    param([int]$ApiPort)

    try {
        $response = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 3
        if ($response -is [bool]) {
            return [bool]$response
        }
        if ($null -ne $response.PSObject.Properties["ok"]) {
            return [bool]$response.ok
        }
    }
    catch {
    }
    return $false
}

function Get-TimelineForPcPythonCommand {
    $venvPython = Join-Path $ProductRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        return [pscustomobject]@{ FilePath = $venvPython; PrefixArguments = @() }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return [pscustomobject]@{ FilePath = $python.Source; PrefixArguments = @() }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return [pscustomobject]@{ FilePath = $python.Source; PrefixArguments = @() }
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return [pscustomobject]@{ FilePath = $py.Source; PrefixArguments = @("-3.11") }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return [pscustomobject]@{ FilePath = $py.Source; PrefixArguments = @("-3.11") }
    }

    throw "Python 3.11 or newer was not found."
}

function Get-TimelineForPcConfiguredPort {
    param([int]$OverridePort)

    if (($OverridePort -lt 0) -or ($OverridePort -gt 65535)) {
        throw "TimelineForPC health API port must be between 1 and 65535."
    }
    if ($OverridePort -gt 0) {
        return $OverridePort
    }

    $settingsPath = Join-Path $ProductRoot "settings.json"
    if (Test-Path -LiteralPath $settingsPath -PathType Leaf) {
        try {
            $settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $apiPortText = ""
            if ($null -ne $settings.PSObject.Properties["runtime"] -and $null -ne $settings.runtime) {
                if ($null -ne $settings.runtime.PSObject.Properties["apiPort"]) {
                    $apiPortText = [string]$settings.runtime.apiPort
                }
                elseif ($null -ne $settings.runtime.PSObject.Properties["api_port"]) {
                    $apiPortText = [string]$settings.runtime.api_port
                }
            }
            elseif ($null -ne $settings.PSObject.Properties["apiPort"]) {
                $apiPortText = [string]$settings.apiPort
            }

            $parsedPort = 19600
            if ([int]::TryParse($apiPortText, [ref]$parsedPort) -and $parsedPort -ge 1 -and $parsedPort -le 65535) {
                return $parsedPort
            }
        }
        catch {
        }
    }

    return 19600
}

function Set-TimelineForPcApiEnvironment {
    param([int]$ApiPort)

    $currentPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
    if ([string]::IsNullOrWhiteSpace($currentPythonPath)) {
        Set-Item -Path "Env:PYTHONPATH" -Value $SourceRoot
    }
    elseif ($currentPythonPath.Split([System.IO.Path]::PathSeparator) -notcontains $SourceRoot) {
        Set-Item -Path "Env:PYTHONPATH" -Value ($SourceRoot + [System.IO.Path]::PathSeparator + $currentPythonPath)
    }
    Set-Item -Path "Env:TIMELINE_FOR_PC_ROOT" -Value $ProductRoot
    Set-Item -Path "Env:TIMELINE_FOR_PC_API_PORT" -Value ([string]$ApiPort)
}

if (-not (Test-Path -LiteralPath $ApiModulePath -PathType Leaf)) {
    throw "TimelineForPC API module was not found: $ApiModulePath"
}

$ApiPort = Get-TimelineForPcConfiguredPort -OverridePort $Port
$Python = Get-TimelineForPcPythonCommand
Set-TimelineForPcApiEnvironment -ApiPort $ApiPort

if (-not (Test-TimelineForPcApiHealth -ApiPort $ApiPort)) {
    foreach ($stale in @(Get-TimelineForPcApiModuleProcesses)) {
        Stop-TimelineForPcProcessTree -RootProcessId ([int]$stale.ProcessId)
    }
    if (Test-Path -LiteralPath $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force
    }
}

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
            if (Test-TimelineForPcApiCommandLine -CommandLine $commandLine) {
                Write-Host "TimelineForPC local API is already running. pid=$existingPid"
                exit 0
            }
        }
    }
    Remove-Item -LiteralPath $PidFile -Force
}

$running = Get-TimelineForPcApiProcess
if ($null -ne $running) {
    Set-Content -LiteralPath $PidFile -Value ([string]$running.ProcessId) -Encoding ASCII
    Write-Host "TimelineForPC local API is already running. pid=$($running.ProcessId)"
    exit 0
}

$healthArgs = @($Python.PrefixArguments) + @(
    "-m",
    "timeline_for_pc.api_server",
    "--product-root",
    $ProductRoot,
    "--port",
    [string]$ApiPort
)

$previousProductRoot = $env:TIMELINE_FOR_PC_ROOT
$previousApiPort = $env:TIMELINE_FOR_PC_API_PORT
$env:TIMELINE_FOR_PC_ROOT = $ProductRoot
$env:TIMELINE_FOR_PC_API_PORT = [string]$ApiPort

if ($Foreground) {
    try {
        & $Python.FilePath @healthArgs
        exit $LASTEXITCODE
    }
    finally {
        if ($null -eq $previousProductRoot) {
            Remove-Item Env:TIMELINE_FOR_PC_ROOT -ErrorAction SilentlyContinue
        }
        else {
            $env:TIMELINE_FOR_PC_ROOT = $previousProductRoot
        }
        if ($null -eq $previousApiPort) {
            Remove-Item Env:TIMELINE_FOR_PC_API_PORT -ErrorAction SilentlyContinue
        }
        else {
            $env:TIMELINE_FOR_PC_API_PORT = $previousApiPort
        }
    }
}

$process = Start-Process -FilePath $Python.FilePath -ArgumentList $healthArgs -WorkingDirectory $ProductRoot -WindowStyle Hidden -PassThru
if ($null -eq $previousProductRoot) {
    Remove-Item Env:TIMELINE_FOR_PC_ROOT -ErrorAction SilentlyContinue
}
else {
    $env:TIMELINE_FOR_PC_ROOT = $previousProductRoot
}
if ($null -eq $previousApiPort) {
    Remove-Item Env:TIMELINE_FOR_PC_API_PORT -ErrorAction SilentlyContinue
}
else {
    $env:TIMELINE_FOR_PC_API_PORT = $previousApiPort
}
Set-Content -LiteralPath $PidFile -Value ([string]$process.Id) -Encoding ASCII
Write-Host "TimelineForPC local API started. pid=$($process.Id)"
