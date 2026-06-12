$ErrorActionPreference = "Stop"

function Safe-Command {
    param(
        [scriptblock]$Script,
        $Fallback
    )

    try {
        return & $Script
    }
    catch {
        return $Fallback
    }
}

function To-IntOrNull {
    param($Value)
    if ($null -eq $Value -or $Value -eq "") {
        return $null
    }
    try {
        return [int64]$Value
    }
    catch {
        return $null
    }
}

function To-DoubleOrNull {
    param($Value)
    if ($null -eq $Value -or $Value -eq "") {
        return $null
    }
    try {
        return [double]$Value
    }
    catch {
        return $null
    }
}

function Format-DateValue {
    param($Value)
    if ($null -eq $Value) {
        return $null
    }
    try {
        return ([datetime]$Value).ToString("yyyy-MM-dd HH:mm:ss K")
    }
    catch {
        return [string]$Value
    }
}

function Decode-MonitorString {
    param($Chars)
    if ($null -eq $Chars) {
        return $null
    }
    return (($Chars | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ }) -join "").Trim()
}

$computerInfo = Safe-Command {
    Get-ComputerInfo | Select-Object CsName, WindowsProductName, WindowsVersion, OsBuildNumber, CsSystemType, HyperVisorPresent
} $null

$registry = Safe-Command {
    Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
} $null

$operatingSystem = Safe-Command {
    Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture, InstallDate, LastBootUpTime
} $null

$computerSystem = Safe-Command {
    Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory, Domain, Workgroup, NumberOfProcessors
} $null

$computerSystemProduct = Safe-Command {
    Get-CimInstance Win32_ComputerSystemProduct | Select-Object UUID
} $null

$baseBoard = Safe-Command {
    Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product
} $null

$bios = Safe-Command {
    Get-CimInstance Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion, ReleaseDate
} $null

$systemEnclosure = Safe-Command {
    Get-CimInstance Win32_SystemEnclosure | Select-Object ChassisTypes
} $null

$processors = Safe-Command {
    @(Get-CimInstance Win32_Processor | ForEach-Object {
        [ordered]@{
            name = [string]$_.Name
            cores = $_.NumberOfCores
            logical_processors = $_.NumberOfLogicalProcessors
            max_clock_mhz = $_.MaxClockSpeed
            socket = [string]$_.SocketDesignation
            l2_cache_kb = $_.L2CacheSize
            l3_cache_kb = $_.L3CacheSize
        }
    })
} @()

$memoryModules = Safe-Command {
    @(Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
        $configured = $null
        if ($_.ConfiguredClockSpeed) {
            $configured = [int]$_.ConfiguredClockSpeed
        }
        elseif ($_.Speed) {
            $configured = [int]$_.Speed
        }

        [ordered]@{
            size_bytes = To-IntOrNull $_.Capacity
            part_number = ([string]$_.PartNumber).Trim()
            speed_mt_s = $configured
            manufacturer = ([string]$_.Manufacturer).Trim()
        }
    })
} @()

$memoryArray = Safe-Command {
    Get-CimInstance Win32_PhysicalMemoryArray | Select-Object MemoryDevices, MaxCapacityEx, MaxCapacity
} $null

$gpus = Safe-Command {
    @(Get-CimInstance Win32_VideoController | ForEach-Object {
        [ordered]@{
            name = [string]$_.Name
            driver_version = [string]$_.DriverVersion
            adapter_ram_bytes = To-IntOrNull $_.AdapterRAM
            current_horizontal_resolution = To-IntOrNull $_.CurrentHorizontalResolution
            current_vertical_resolution = To-IntOrNull $_.CurrentVerticalResolution
            current_refresh_rate = To-IntOrNull $_.CurrentRefreshRate
        }
    })
} @()

$monitorNames = Safe-Command {
    @(Get-PnpDevice -Class Monitor | ForEach-Object {
        $name = ([string]$_.FriendlyName).Trim()
        if ($name) {
            $name
        }
    })
} @()

$physicalDisks = Safe-Command {
    @(Get-PhysicalDisk | ForEach-Object {
        [ordered]@{
            name = [string]$_.FriendlyName
            media_type = [string]$_.MediaType
            bus_type = [string]$_.BusType
            size_bytes = To-IntOrNull $_.Size
            health_status = [string]$_.HealthStatus
        }
    })
} @()

$volumes = Safe-Command {
    @(Get-PSDrive -PSProvider FileSystem | ForEach-Object {
        $used = $null
        if ($_.Used -ne $null) {
            $used = [int64]$_.Used
        }
        $free = $null
        if ($_.Free -ne $null) {
            $free = [int64]$_.Free
        }

        $total = $null
        if ($used -ne $null -and $free -ne $null) {
            $total = $used + $free
        }

        [ordered]@{
            name = [string]$_.Name
            root = [string]$_.Root
            used_bytes = $used
            free_bytes = $free
            total_bytes = $total
        }
    })
} @()

$systemPartitionCount = Safe-Command {
    @(
        Get-Partition |
            Where-Object {
                $_.DriveLetter -eq $null -and
                $_.Size -ne $null -and
                $_.Size -lt 10GB
            }
    ).Count
} $null

$uninstallPaths = @(
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*"
)

$applications = Safe-Command {
    @(Get-ItemProperty -Path $uninstallPaths -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName } |
        ForEach-Object {
            [ordered]@{
                name = [string]$_.DisplayName
                version = [string]$_.DisplayVersion
                publisher = [string]$_.Publisher
            }
        })
} @()

$audioDevices = Safe-Command {
    @(Get-CimInstance Win32_SoundDevice | ForEach-Object { [string]$_.Name })
} @()

$networkAdapters = Safe-Command {
    @(Get-NetAdapter | Sort-Object InterfaceDescription | ForEach-Object {
        $kind = "other"
        $description = [string]$_.InterfaceDescription
        if ($description -match "Wi-Fi|Wireless") {
            $kind = "wifi"
        }
        elseif ($_.HardwareInterface) {
            $kind = "physical"
        }
        elseif ($description -match "Hyper-V|Virtual|WSL|vEthernet") {
            $kind = "virtual"
        }

        [ordered]@{
            name = [string]$_.Name
            description = $description
            kind = $kind
            status = [string]$_.Status
            link_speed = [string]$_.LinkSpeed
        }
    })
} @()

$hotfixes = Safe-Command {
    @(Get-HotFix | Sort-Object InstalledOn -Descending | ForEach-Object { [string]$_.HotFixID })
} @()

$nvidiaRuntime = Safe-Command {
    $lines = @(cmd.exe /c "nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,memory.free,temperature.gpu,power.draw,power.limit,fan.speed,clocks.gr,clocks.mem,vbios_version,pci.bus_id,pcie.link.gen.current,pcie.link.gen.max --format=csv,noheader,nounits 2>nul")
    $items = @()
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line -match "not found|NVIDIA-SMI") {
            continue
        }
        $parts = $line -split "\s*,\s*"
        if ($parts.Count -lt 15) {
            continue
        }
        $items += [ordered]@{
            name = $parts[0]
            driver_version_display = $parts[1]
            vram_total_mib = To-IntOrNull $parts[2]
            used_vram_mib = To-IntOrNull $parts[3]
            free_vram_mib = To-IntOrNull $parts[4]
            temperature_c = To-IntOrNull $parts[5]
            power_draw_w = To-DoubleOrNull $parts[6]
            power_limit_w = To-DoubleOrNull $parts[7]
            fan_percent = To-DoubleOrNull $parts[8]
            graphics_clock_mhz = To-IntOrNull $parts[9]
            memory_clock_mhz = To-IntOrNull $parts[10]
            vbios_version = $parts[11]
            pci_bus_id = $parts[12]
            pcie_link_gen_current = To-IntOrNull $parts[13]
            pcie_link_gen_max = To-IntOrNull $parts[14]
        }
    }
    $items
} @()

$wslStatusLines = Safe-Command {
    @((cmd.exe /u /c "wsl.exe --status") | ForEach-Object { ([string]$_) -replace "`0", "" })
} @()

$wslStatusText = ($wslStatusLines -join "`n")
$wslDefaultDistribution = $null
$wslDefaultVersion = $null
$wslKernel = $null

if ($wslStatusText -match "Default Distribution:\s*(.+)") {
    $wslDefaultDistribution = $Matches[1].Trim()
}
elseif ($wslStatusText -match "既定のディストリビューション:\s*(.+)") {
    $wslDefaultDistribution = $Matches[1].Trim()
}

if ($wslStatusText -match "Default Version:\s*(\d+)") {
    $wslDefaultVersion = To-IntOrNull $Matches[1]
}
elseif ($wslStatusText -match "既定のバージョン:\s*(\d+)") {
    $wslDefaultVersion = To-IntOrNull $Matches[1]
}

if ($wslStatusText -match "Kernel version:\s*(.+)") {
    $wslKernel = $Matches[1].Trim()
}
elseif ($wslStatusText -match "カーネル バージョン:\s*(.+)") {
    $wslKernel = $Matches[1].Trim()
}

$wslDistributions = @()
$wslRunningDistributions = @()
$wslListLines = Safe-Command {
    @((cmd.exe /u /c "wsl.exe -l -v") | ForEach-Object { ([string]$_) -replace "`0", "" })
} @()

foreach ($line in $wslListLines) {
    $trimmed = $line.Trim()
    if (-not $trimmed) {
        continue
    }
    if ($trimmed -match "NAME\s+STATE\s+VERSION") {
        continue
    }
    $clean = $trimmed -replace "^\*", ""
    $columns = $clean -split "\s{2,}"
    if ($columns.Count -lt 3) {
        continue
    }
    $entry = [ordered]@{
        name = $columns[0].Trim()
        state = $columns[1].Trim()
        version = To-IntOrNull $columns[2].Trim()
    }
    $wslDistributions += $entry
    if ($entry.state -eq "Running") {
        $wslRunningDistributions += $entry.name
    }
}

$wslLinuxRelease = $null
if ($wslDefaultDistribution) {
    $linuxLines = Safe-Command {
        @((cmd.exe /c "wsl.exe -d $wslDefaultDistribution sh -lc ""source /etc/os-release >/dev/null 2>&1; echo \${PRETTY_NAME:-unknown}; uname -r""") | ForEach-Object { ([string]$_).Trim() })
    } @()
    if ($linuxLines.Count -ge 1) {
        $wslLinuxRelease = $linuxLines[0].Trim()
    }
    if (-not $wslKernel -and $linuxLines.Count -ge 2) {
        $wslKernel = $linuxLines[1].Trim()
    }
}

$memorySlotsTotal = $null
$memoryMaxCapacityBytes = $null
if ($memoryArray) {
    $memorySlotsTotal = To-IntOrNull $memoryArray.MemoryDevices
    if ($memoryArray.MaxCapacityEx) {
        $memoryMaxCapacityBytes = To-IntOrNull $memoryArray.MaxCapacityEx
    }
    elseif ($memoryArray.MaxCapacity) {
        $memoryMaxCapacityBytes = (To-IntOrNull $memoryArray.MaxCapacity) * 1024
    }
}

$memoryConfiguredSpeed = $null
if ($memoryModules.Count -gt 0) {
    $memoryConfiguredSpeed = $memoryModules[0].speed_mt_s
}

$memoryNotes = @()
if ($memoryConfiguredSpeed -and $memoryConfiguredSpeed -lt 3000) {
    if ($memoryModules | Where-Object { $_.part_number -match "3200" }) {
        $memoryNotes += "The DIMM part number suggests DDR4-3200, but the current configured speed is $memoryConfiguredSpeed MT/s."
    }
}

$primaryGpu = $gpus | Select-Object -First 1
$primaryResolution = $null
$primaryRefreshRate = $null
if ($primaryGpu) {
    if ($primaryGpu.current_horizontal_resolution -and $primaryGpu.current_vertical_resolution) {
        $primaryResolution = "$($primaryGpu.current_horizontal_resolution) x $($primaryGpu.current_vertical_resolution)"
    }
    if ($primaryGpu.current_refresh_rate) {
        $primaryRefreshRate = $primaryGpu.current_refresh_rate
    }
}

$physicalTotalBytes = 0
foreach ($disk in $physicalDisks) {
    if ($disk.size_bytes) {
        $physicalTotalBytes += [int64]$disk.size_bytes
    }
}

$wmiProductName = $null
if ($operatingSystem -and $operatingSystem.Caption) {
    $wmiProductName = ([string]$operatingSystem.Caption).Replace("Microsoft ", "").Trim()
}

$registryProductName = $null
$editionId = $null
$buildLabel = $null
if ($registry) {
    $registryProductName = [string]$registry.ProductName
    $editionId = [string]$registry.EditionID
    if ($registry.CurrentBuildNumber -and $registry.UBR -ne $null) {
        $buildLabel = "$($registry.CurrentBuildNumber).$($registry.UBR)"
    }
}

$osNotes = @()
if ($registryProductName -and $wmiProductName -and $registryProductName -notlike "*$wmiProductName*" -and $wmiProductName -notlike "*$registryProductName*") {
    $osNotes += "ProductName mismatch was detected between registry and WMI."
}

$result = [ordered]@{
    captured_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    os = [ordered]@{
        product_name = if ($wmiProductName) { $wmiProductName } elseif ($registryProductName) { $registryProductName } elseif ($computerInfo) { [string]$computerInfo.WindowsProductName } else { $null }
        version = if ($computerInfo) { [string]$computerInfo.WindowsVersion } elseif ($operatingSystem) { [string]$operatingSystem.Version } else { $null }
        build_number = if ($buildLabel) { $buildLabel } elseif ($computerInfo) { [string]$computerInfo.OsBuildNumber } elseif ($operatingSystem) { [string]$operatingSystem.BuildNumber } else { $null }
        architecture = if ($operatingSystem) { [string]$operatingSystem.OSArchitecture } elseif ($computerInfo) { [string]$computerInfo.CsSystemType } else { $null }
    }
    host = [ordered]@{
        name = if ($computerInfo) { [string]$computerInfo.CsName } else { $env:COMPUTERNAME }
        manufacturer = if ($computerSystem) { [string]$computerSystem.Manufacturer } else { $null }
        model = if ($computerSystem) { [string]$computerSystem.Model } else { $null }
        system_type = if ($computerInfo) { [string]$computerInfo.CsSystemType } else { $null }
        total_memory_bytes = if ($computerSystem) { To-IntOrNull $computerSystem.TotalPhysicalMemory } else { $null }
        motherboard = [ordered]@{
            manufacturer = if ($baseBoard) { [string]$baseBoard.Manufacturer } else { $null }
            product = if ($baseBoard) { [string]$baseBoard.Product } else { $null }
        }
    }
    processors = @(
        $processors | ForEach-Object {
            [ordered]@{
                name = $_.name
                cores = $_.cores
                logical_processors = $_.logical_processors
                max_clock_mhz = $_.max_clock_mhz
            }
        }
    )
    gpus = @(
        $gpus | ForEach-Object {
            [ordered]@{
                name = $_.name
                driver_version = $_.driver_version
                adapter_ram_bytes = $_.adapter_ram_bytes
            }
        }
    )
    physical_disks = $physicalDisks
    volumes = $volumes
    applications = $applications
    details = [ordered]@{
        platform = [ordered]@{
            computer_name = if ($computerInfo) { [string]$computerInfo.CsName } else { $env:COMPUTERNAME }
            uuid = if ($computerSystemProduct) { [string]$computerSystemProduct.UUID } else { $null }
            domain_or_workgroup = if ($computerSystem -and $computerSystem.Workgroup) { [string]$computerSystem.Workgroup } elseif ($computerSystem) { [string]$computerSystem.Domain } else { $null }
        }
        bios = [ordered]@{
            vendor = if ($bios) { [string]$bios.Manufacturer } else { $null }
            version = if ($bios) { [string]$bios.SMBIOSBIOSVersion } else { $null }
            release_date = if ($bios) { Format-DateValue $bios.ReleaseDate } else { $null }
        }
        chassis = [ordered]@{
            types = if ($systemEnclosure) { @($systemEnclosure.ChassisTypes) } else { @() }
        }
        os_details = [ordered]@{
            wmi_product_name = $wmiProductName
            registry_product_name = $registryProductName
            edition_id = $editionId
            build_label = $buildLabel
            install_date_local = if ($operatingSystem) { Format-DateValue $operatingSystem.InstallDate } else { $null }
            last_boot_local = if ($operatingSystem) { Format-DateValue $operatingSystem.LastBootUpTime } else { $null }
            hotfixes = $hotfixes
            notes = $osNotes
        }
        cpu_details = [ordered]@{
            socket = if ($processors.Count -gt 0) { $processors[0].socket } else { $null }
            l2_cache_kb = if ($processors.Count -gt 0) { $processors[0].l2_cache_kb } else { $null }
            l3_cache_kb = if ($processors.Count -gt 0) { $processors[0].l3_cache_kb } else { $null }
            physical_packages = if ($computerSystem) { To-IntOrNull $computerSystem.NumberOfProcessors } else { $null }
        }
        memory_details = [ordered]@{
            slots_used = $memoryModules.Count
            slots_total = $memorySlotsTotal
            configured_speed_mt_s = $memoryConfiguredSpeed
            max_capacity_bytes = $memoryMaxCapacityBytes
            modules = $memoryModules
            notes = $memoryNotes
        }
        gpu_runtime = $nvidiaRuntime
        display = [ordered]@{
            monitor_name = if ($monitorNames.Count -gt 0) { $monitorNames[0] } else { $null }
            resolution = $primaryResolution
            refresh_hz = $primaryRefreshRate
        }
        storage_details = [ordered]@{
            physical_total_bytes = if ($physicalTotalBytes -gt 0) { $physicalTotalBytes } else { $null }
            small_system_partition_count = $systemPartitionCount
        }
        network = [ordered]@{
            adapters = $networkAdapters
        }
        audio = [ordered]@{
            devices = $audioDevices
        }
        virtualization = [ordered]@{
            hypervisor_present = if ($computerInfo) { [bool]$computerInfo.HyperVisorPresent } else { $null }
        }
        wsl = [ordered]@{
            default_distribution = $wslDefaultDistribution
            default_version = $wslDefaultVersion
            running_distributions = $wslRunningDistributions
            distributions = $wslDistributions
            linux_release = $wslLinuxRelease
            kernel = $wslKernel
        }
    }
}

$result | ConvertTo-Json -Depth 10
