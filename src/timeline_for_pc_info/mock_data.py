from __future__ import annotations

from timeline_for_pc_info.models import ApplicationInfo
from timeline_for_pc_info.models import GpuInfo
from timeline_for_pc_info.models import HostInfo
from timeline_for_pc_info.models import MotherboardInfo
from timeline_for_pc_info.models import OsInfo
from timeline_for_pc_info.models import PhysicalDiskInfo
from timeline_for_pc_info.models import ProcessorInfo
from timeline_for_pc_info.models import SCHEMA_VERSION
from timeline_for_pc_info.models import Snapshot
from timeline_for_pc_info.models import VolumeInfo


def get_mock_snapshot(profile: str) -> Snapshot:
    if profile == "baseline":
        return Snapshot(
            schema_version=SCHEMA_VERSION,
            captured_at_utc="2026-04-20T00:00:00Z",
            capture_mode="mock",
            os=OsInfo(
                product_name="Windows 10 Pro",
                version="2009",
                build_number="26100",
                architecture="x64-based PC",
            ),
            host=HostInfo(
                name="DESKTOP-MOCK",
                manufacturer="ASUS",
                model="PRIME H570M-PLUS",
                system_type="x64-based PC",
                total_memory_bytes=17179869184,
                motherboard=MotherboardInfo(
                    manufacturer="ASUSTeK COMPUTER INC.",
                    product="PRIME H570M-PLUS",
                ),
            ),
            processors=(
                ProcessorInfo(
                    name="11th Gen Intel(R) Core(TM) i7-11700 @ 2.50GHz",
                    cores=8,
                    logical_processors=16,
                    max_clock_mhz=2496,
                ),
            ),
            gpus=(
                GpuInfo(
                    name="NVIDIA GeForce RTX 4070",
                    driver_version="32.0.15.9000",
                    adapter_ram_bytes=12884901888,
                ),
            ),
            physical_disks=(
                PhysicalDiskInfo(
                    name="WD_BLACK SN770 1TB",
                    media_type="SSD",
                    bus_type="NVMe",
                    size_bytes=1000204886016,
                    health_status="Healthy",
                ),
                PhysicalDiskInfo(
                    name="TOSHIBA DT01ACA200",
                    media_type="HDD",
                    bus_type="SATA",
                    size_bytes=2000398934016,
                    health_status="Healthy",
                ),
            ),
            volumes=(
                VolumeInfo(
                    name="C",
                    root="C:\\",
                    used_bytes=500000000000,
                    free_bytes=300000000000,
                    total_bytes=800000000000,
                ),
                VolumeInfo(
                    name="D",
                    root="D:\\",
                    used_bytes=900000000000,
                    free_bytes=700000000000,
                    total_bytes=1600000000000,
                ),
            ),
            applications=_apps(
                ("Python 3.11.7", "3.11.7150.0", "Python Software Foundation"),
                ("Git", "2.49.0", "The Git Development Community"),
                ("Visual Studio Code", "1.98.2", "Microsoft Corporation"),
                ("Google Chrome", "135.0.1", "Google LLC"),
                ("7-Zip", "24.09", "Igor Pavlov"),
            ),
            details={
                "platform": {
                    "computer_name": "DESKTOP-MOCK",
                    "uuid": "00000000-0000-0000-0000-000000000001",
                    "domain_or_workgroup": "WORKGROUP",
                },
                "bios": {
                    "vendor": "American Megatrends Inc.",
                    "version": "1030",
                    "release_date": "2021-08-09",
                },
                "chassis": {"types": [3]},
                "os_details": {
                    "wmi_product_name": "Microsoft Windows 11 Pro",
                    "registry_product_name": "Windows 10 Pro 25H2",
                    "edition_id": "Professional",
                    "build_label": "26100.1000",
                    "install_date_local": "2026-04-01 09:00:00 JST",
                    "last_boot_local": "2026-04-19 07:10:00 JST",
                    "hotfixes": ["KB5000001", "KB5000002"],
                    "notes": ["ProductName mismatch was detected between registry and WMI."],
                },
                "cpu_details": {
                    "socket": "LGA1200",
                    "l2_cache_kb": 4096,
                    "l3_cache_kb": 16384,
                    "physical_packages": 1,
                },
                "memory_details": {
                    "slots_used": 2,
                    "slots_total": 4,
                    "configured_speed_mt_s": 2133,
                    "max_capacity_bytes": 68719476736,
                    "modules": [
                        {"size_bytes": 8589934592, "part_number": "Corsair CMK16GX4M1E3200C16", "speed_mt_s": 2133},
                        {"size_bytes": 8589934592, "part_number": "Corsair CMK16GX4M1E3200C16", "speed_mt_s": 2133},
                    ],
                    "notes": ["The DIMM part number suggests DDR4-3200, but the current configured speed is 2133 MT/s."],
                },
                "gpu_runtime": [
                    {
                        "name": "NVIDIA GeForce RTX 4070",
                        "driver_version_display": "591.00",
                        "vram_total_mib": 12282,
                        "temperature_c": 44,
                        "used_vram_mib": 800,
                        "free_vram_mib": 11482,
                    }
                ],
                "display": {
                    "monitor_name": "Dell U2720QM",
                    "resolution": "3840 x 2160",
                    "refresh_hz": 60,
                },
                "storage_details": {
                    "physical_total_bytes": 3000603820032,
                    "small_system_partition_count": 2,
                },
                "network": {
                    "adapters": [
                        {
                            "name": "Intel(R) Ethernet Connection (14) I219-V",
                            "kind": "physical",
                            "status": "Up",
                            "link_speed": "1 Gbps",
                        }
                    ]
                },
                "audio": {"devices": ["NVIDIA High Definition Audio", "USB オーディオ 2.0"]},
                "virtualization": {"hypervisor_present": True},
                "wsl": {
                    "default_distribution": "Ubuntu",
                    "default_version": 2,
                    "running_distributions": ["Ubuntu"],
                    "linux_release": "Ubuntu 24.04 LTS",
                    "kernel": "6.6.87.2-microsoft-standard-WSL2",
                },
            },
        )

    if profile == "upgraded":
        return Snapshot(
            schema_version=SCHEMA_VERSION,
            captured_at_utc="2026-05-01T00:00:00Z",
            capture_mode="mock",
            os=OsInfo(
                product_name="Windows 10 Pro",
                version="2009",
                build_number="26200",
                architecture="x64-based PC",
            ),
            host=HostInfo(
                name="DESKTOP-MOCK",
                manufacturer="ASUS",
                model="PRIME H570M-PLUS",
                system_type="x64-based PC",
                total_memory_bytes=34359738368,
                motherboard=MotherboardInfo(
                    manufacturer="ASUSTeK COMPUTER INC.",
                    product="PRIME H570M-PLUS",
                ),
            ),
            processors=(
                ProcessorInfo(
                    name="11th Gen Intel(R) Core(TM) i7-11700 @ 2.50GHz",
                    cores=8,
                    logical_processors=16,
                    max_clock_mhz=2496,
                ),
            ),
            gpus=(
                GpuInfo(
                    name="NVIDIA GeForce RTX 4070",
                    driver_version="32.0.15.9186",
                    adapter_ram_bytes=12884901888,
                ),
            ),
            physical_disks=(
                PhysicalDiskInfo(
                    name="WD_BLACK SN770 1TB",
                    media_type="SSD",
                    bus_type="NVMe",
                    size_bytes=1000204886016,
                    health_status="Healthy",
                ),
                PhysicalDiskInfo(
                    name="TOSHIBA DT01ACA200",
                    media_type="HDD",
                    bus_type="SATA",
                    size_bytes=2000398934016,
                    health_status="Healthy",
                ),
                PhysicalDiskInfo(
                    name="WD_BLACK SN750 SE 1TB",
                    media_type="SSD",
                    bus_type="NVMe",
                    size_bytes=1000204886016,
                    health_status="Healthy",
                ),
            ),
            volumes=(
                VolumeInfo(
                    name="C",
                    root="C:\\",
                    used_bytes=540000000000,
                    free_bytes=260000000000,
                    total_bytes=800000000000,
                ),
                VolumeInfo(
                    name="D",
                    root="D:\\",
                    used_bytes=950000000000,
                    free_bytes=650000000000,
                    total_bytes=1600000000000,
                ),
                VolumeInfo(
                    name="E",
                    root="E:\\",
                    used_bytes=150000000000,
                    free_bytes=850000000000,
                    total_bytes=1000000000000,
                ),
            ),
            applications=_apps(
                ("Python 3.11.8", "3.11.8150.0", "Python Software Foundation"),
                ("Git", "2.49.0", "The Git Development Community"),
                ("Visual Studio Code", "1.99.0", "Microsoft Corporation"),
                ("Google Chrome", "136.0.1", "Google LLC"),
                ("Docker Desktop", "4.41.0", "Docker Inc."),
                ("Ollama", "0.6.2", "Ollama"),
            ),
            details={
                "platform": {
                    "computer_name": "DESKTOP-MOCK",
                    "uuid": "00000000-0000-0000-0000-000000000001",
                    "domain_or_workgroup": "WORKGROUP",
                },
                "bios": {
                    "vendor": "American Megatrends Inc.",
                    "version": "1030",
                    "release_date": "2021-08-09",
                },
                "chassis": {"types": [3]},
                "os_details": {
                    "wmi_product_name": "Microsoft Windows 11 Pro",
                    "registry_product_name": "Windows 10 Pro 25H2",
                    "edition_id": "Professional",
                    "build_label": "26200.8037",
                    "install_date_local": "2026-04-01 09:00:00 JST",
                    "last_boot_local": "2026-04-20 08:00:00 JST",
                    "hotfixes": ["KB5066128", "KB5054156", "KB5071430"],
                    "notes": ["ProductName mismatch was detected between registry and WMI."],
                },
                "cpu_details": {
                    "socket": "LGA1200",
                    "l2_cache_kb": 4096,
                    "l3_cache_kb": 16384,
                    "physical_packages": 1,
                },
                "memory_details": {
                    "slots_used": 2,
                    "slots_total": 4,
                    "configured_speed_mt_s": 2133,
                    "max_capacity_bytes": 68719476736,
                    "modules": [
                        {"size_bytes": 17179869184, "part_number": "Corsair CMK32GX4M2E3200C16", "speed_mt_s": 2133},
                        {"size_bytes": 17179869184, "part_number": "Corsair CMK32GX4M2E3200C16", "speed_mt_s": 2133},
                    ],
                    "notes": ["The DIMM part number suggests DDR4-3200, but the current configured speed is 2133 MT/s."],
                },
                "gpu_runtime": [
                    {
                        "name": "NVIDIA GeForce RTX 4070",
                        "driver_version_display": "591.86",
                        "vram_total_mib": 12282,
                        "temperature_c": 46,
                        "used_vram_mib": 1595,
                        "free_vram_mib": 10418,
                        "power_draw_w": 36.37,
                        "power_limit_w": 200.0,
                    }
                ],
                "display": {
                    "monitor_name": "Dell U2720QM",
                    "resolution": "3840 x 2160",
                    "refresh_hz": 60,
                },
                "storage_details": {
                    "physical_total_bytes": 6001207640064,
                    "small_system_partition_count": 2,
                },
                "network": {
                    "adapters": [
                        {
                            "name": "Intel(R) Ethernet Connection (14) I219-V",
                            "kind": "physical",
                            "status": "Up",
                            "link_speed": "1 Gbps",
                        },
                        {
                            "name": "vEthernet (WSL)",
                            "kind": "virtual",
                            "status": "Up",
                            "link_speed": "10 Gbps",
                        },
                    ]
                },
                "audio": {
                    "devices": [
                        "NVIDIA High Definition Audio",
                        "USB Audio 2.0",
                        "High Definition Audio デバイス",
                    ]
                },
                "virtualization": {"hypervisor_present": True},
                "wsl": {
                    "default_distribution": "Ubuntu",
                    "default_version": 2,
                    "running_distributions": ["Ubuntu", "docker-desktop"],
                    "linux_release": "Ubuntu 24.04.4 LTS",
                    "kernel": "6.6.87.2-microsoft-standard-WSL2",
                },
            },
        )

    raise ValueError(f"Unknown mock profile: {profile}")


def _apps(*items: tuple[str, str, str]) -> tuple[ApplicationInfo, ...]:
    return tuple(
        ApplicationInfo(name=name, version=version, publisher=publisher)
        for name, version, publisher in items
    )
