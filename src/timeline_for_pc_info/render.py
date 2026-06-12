from __future__ import annotations

from typing import Any

from timeline_for_pc_info.models import Snapshot


CHASSIS_LABELS = {
    3: "Desktop",
    4: "Low Profile Desktop",
    6: "Mini Tower",
    7: "Tower",
    13: "All-in-One",
    23: "Rack Mount",
}


def render_report(snapshot: Snapshot) -> str:
    details = snapshot.details
    platform = _dict(details, "platform")
    bios = _dict(details, "bios")
    chassis = _dict(details, "chassis")
    os_details = _dict(details, "os_details")
    cpu_details = _dict(details, "cpu_details")
    memory_details = _dict(details, "memory_details")
    display = _dict(details, "display")
    storage_details = _dict(details, "storage_details")
    network = _dict(details, "network")
    audio = _dict(details, "audio")
    virtualization = _dict(details, "virtualization")
    wsl = _dict(details, "wsl")
    gpu_runtime = _list(details, "gpu_runtime")

    lines = [
        "# TimelineForPcInfo",
        "",
        f"Captured at: {snapshot.captured_at_utc}",
        "",
        "## System",
        f"- PC name: {_or(platform.get('computer_name'), snapshot.host.name, 'unknown')}",
        f"- Manufacturer / model: {_join_non_empty(snapshot.host.manufacturer, snapshot.host.model, separator=' / ')}",
        f"- Motherboard: {_join_non_empty(snapshot.host.motherboard.manufacturer if snapshot.host.motherboard else None, snapshot.host.motherboard.product if snapshot.host.motherboard else None)}",
        f"- BIOS: {_join_non_empty(bios.get('vendor'), bios.get('version'), separator=' / ')}",
        f"- BIOS release date: {_or(bios.get('release_date'), 'unknown')}",
        f"- Chassis: {_chassis_label(chassis)}",
        f"- Domain / workgroup: {_or(platform.get('domain_or_workgroup'), 'unknown')}",
        "",
        "## OS",
        f"- Windows: {_join_non_empty(snapshot.os.product_name, 'Build ' + str(snapshot.os.build_number) if snapshot.os.build_number else None, _normalize_architecture(snapshot.os.architecture), separator=' / ')}",
        f"- WMI product name: {_or(os_details.get('wmi_product_name'), 'unknown')}",
        f"- Registry product name: {_or(os_details.get('registry_product_name'), 'unknown')}",
        f"- Edition ID: {_or(os_details.get('edition_id'), 'unknown')}",
        f"- Installed at: {_or(os_details.get('install_date_local'), 'unknown')}",
        f"- Last boot: {_or(os_details.get('last_boot_local'), 'unknown')}",
        f"- Hotfixes: {_hotfixes_label(_list(os_details, 'hotfixes'))}",
        f"- OS notes: {_notes_label(_list(os_details, 'notes'))}",
        "",
        "## CPU / Memory / GPU",
        f"- CPU: {_cpu_label(snapshot)}",
        f"- CPU details: {_cpu_details_label(cpu_details, snapshot)}",
        f"- RAM: {_format_bytes(snapshot.host.total_memory_bytes)}",
        f"- Memory layout: {_memory_modules_label(memory_details)}",
        f"- Memory speed: {_or(_optional_mt_s(memory_details.get('configured_speed_mt_s')), 'unknown')}",
        f"- Memory slots: {_slots_label(memory_details)}",
        f"- Memory maximum: {_format_bytes(memory_details.get('max_capacity_bytes'))}",
        f"- Configuration notes: {_notes_label(_list(memory_details, 'notes'))}",
        f"- GPU: {_gpu_summary(snapshot, gpu_runtime)}",
        f"- GPU runtime: {_gpu_runtime_detail_label(gpu_runtime)}",
        "",
        "## Display",
        f"- Monitor: {_or(display.get('monitor_name'), 'unknown')}",
        f"- Output: {_join_non_empty(display.get('resolution'), _optional_hz(display.get('refresh_hz')), separator=' / ')}",
        "",
        "## Storage",
    ]

    for disk in snapshot.physical_disks:
        disk_bits = [disk.name]
        if disk.bus_type or disk.media_type:
            disk_bits.append(_join_non_empty(disk.bus_type, disk.media_type))
        if disk.size_bytes is not None:
            disk_bits.append(_format_bytes(disk.size_bytes))
        lines.append(f"- Physical disk: {' / '.join(bit for bit in disk_bits if bit)}")
    if storage_details.get("physical_total_bytes") is not None:
        lines.append(f"- Total physical capacity: {_format_bytes(storage_details.get('physical_total_bytes'))}")
    if storage_details.get("small_system_partition_count") is not None:
        lines.append(f"- Small system partitions: {storage_details.get('small_system_partition_count')}")
    for volume in snapshot.volumes:
        lines.append(f"- {volume.name}: {_volume_summary(volume.total_bytes, volume.free_bytes)}")

    lines.extend(
        [
            "",
            "## Network / WSL",
        ]
    )

    adapters = _list(network, "adapters")
    for adapter in adapters[:8]:
        if not isinstance(adapter, dict):
            continue
        prefix = {
            "physical": "Ethernet NIC",
            "wifi": "Wi-Fi",
            "virtual": "Virtual NIC",
        }.get(adapter.get("kind"), "NIC")
        summary = _join_non_empty(
            _english_text(adapter.get("description")),
            _english_text(adapter.get("name")),
            adapter.get("status"),
            adapter.get("link_speed"),
            separator=" / ",
        )
        lines.append(f"- {prefix}: {_or(summary, _english_text(adapter.get('name')), 'unknown')}")

    wsl_summary = _join_non_empty(
        _optional_pair("Default distro", wsl.get("default_distribution")),
        _optional_pair("Default version", wsl.get("default_version")),
        separator=", ",
    )
    if wsl_summary:
        lines.append(f"- WSL: {wsl_summary}")
    running = _list(wsl, "running_distributions")
    if running:
        lines.append(f"- Running WSL distros: {', '.join(str(item) for item in running)}")
    if wsl.get("linux_release"):
        lines.append(f"- Linux release: {wsl.get('linux_release')}")
    if wsl.get("kernel"):
        lines.append(f"- WSL kernel: {wsl.get('kernel')}")

    lines.extend(
        [
            "",
            "## Audio / Virtualization",
            f"- Audio devices: {_list_label(_list(audio, 'devices'), limit=8)}",
            f"- Hypervisor present: {_bool_label(virtualization.get('hypervisor_present'))}",
            "",
            "## Installed Apps",
            f"- Installed apps count: {len(snapshot.applications)}",
            f"- Key installed apps: {_key_apps_label(snapshot)}",
        ]
    )

    lines.append("")
    return "\n".join(lines)


def _cpu_label(snapshot: Snapshot) -> str:
    if not snapshot.processors:
        return "Unknown CPU"
    processor = snapshot.processors[0]
    parts = [processor.name]
    if processor.cores is not None and processor.logical_processors is not None:
        parts.append(f"{processor.cores} cores / {processor.logical_processors} threads")
    return " / ".join(parts)


def _gpu_summary(snapshot: Snapshot, gpu_runtime: list[Any]) -> str:
    if gpu_runtime and isinstance(gpu_runtime[0], dict):
        runtime = gpu_runtime[0]
        if runtime.get("name"):
            parts = [str(runtime.get("name"))]
            if runtime.get("vram_total_mib") is not None:
                parts.append(f"VRAM {_format_mib(runtime.get('vram_total_mib'))}")
            if runtime.get("driver_version_display"):
                parts.append(f"driver {runtime.get('driver_version_display')}")
            if runtime.get("temperature_c") is not None:
                parts.append(f"{runtime.get('temperature_c')}°C")
            return " / ".join(parts)
    if snapshot.gpus:
        gpu = snapshot.gpus[0]
        return _join_non_empty(gpu.name, f"driver {gpu.driver_version}" if gpu.driver_version else None, separator=" / ")
    return "Unknown GPU"


def _gpu_runtime_detail_label(gpu_runtime: list[Any]) -> str:
    if not gpu_runtime or not isinstance(gpu_runtime[0], dict):
        return "unknown"
    runtime = gpu_runtime[0]
    details = [
        _optional_pair("VRAM used", _optional_mib(runtime.get("used_vram_mib"))),
        _optional_pair("VRAM free", _optional_mib(runtime.get("free_vram_mib"))),
        _optional_pair("Power draw", _optional_watts(runtime.get("power_draw_w"))),
        _optional_pair("Power limit", _optional_watts(runtime.get("power_limit_w"))),
        _optional_pair("Fan", _optional_percent(runtime.get("fan_percent"))),
        _optional_pair("Graphics clock", _optional_mhz(runtime.get("graphics_clock_mhz"))),
        _optional_pair("Memory clock", _optional_mhz(runtime.get("memory_clock_mhz"))),
        _optional_pair("VBIOS", runtime.get("vbios_version")),
        _optional_pair("PCI bus", runtime.get("pci_bus_id")),
        _optional_pair("PCIe link", _pcie_link_label(runtime)),
    ]
    return _join_values(details)


def _memory_modules_label(memory_details: dict[str, Any]) -> str:
    modules = [item for item in _list(memory_details, "modules") if isinstance(item, dict)]
    if not modules:
        return "unknown"
    size_labels = [_format_bytes(item.get("size_bytes")) for item in modules]
    part_numbers = [str(item.get("part_number")) for item in modules if item.get("part_number")]
    label = " + ".join(size_labels)
    if part_numbers:
        label = f"{label} / {' / '.join(part_numbers[:2])}"
    return label


def _cpu_details_label(cpu_details: dict[str, Any], snapshot: Snapshot) -> str:
    processor = snapshot.processors[0] if snapshot.processors else None
    details = [
        _optional_pair("Socket", cpu_details.get("socket")),
        _optional_pair("Packages", cpu_details.get("physical_packages")),
        _optional_pair("Max clock", _optional_mhz(processor.max_clock_mhz if processor else None)),
        _optional_pair("L2", _optional_kib(cpu_details.get("l2_cache_kb"))),
        _optional_pair("L3", _optional_kib(cpu_details.get("l3_cache_kb"))),
    ]
    return _join_values(details)


def _slots_label(memory_details: dict[str, Any]) -> str:
    used = memory_details.get("slots_used")
    total = memory_details.get("slots_total")
    if used not in (None, "") and total not in (None, ""):
        return f"{used} / {total}"
    if used not in (None, ""):
        return str(used)
    return "unknown"


def _notes_label(notes: list[Any]) -> str:
    values = [str(item).strip() for item in notes if str(item).strip()]
    if not values:
        return "none"
    return "; ".join(values[:4])


def _hotfixes_label(hotfixes: list[Any]) -> str:
    values = [str(item).strip() for item in hotfixes if str(item).strip()]
    if not values:
        return "unknown"
    head = ", ".join(values[:8])
    suffix = "" if len(values) <= 8 else f", +{len(values) - 8} more"
    return f"{len(values)} installed ({head}{suffix})"


def _key_apps_label(snapshot: Snapshot) -> str:
    keywords = (
        "docker",
        "ollama",
        "visual studio code",
        "git",
        "python",
        "node",
        "nvidia",
        "cuda",
        "chrome",
        "firefox",
        "windows subsystem",
        "wsl",
    )
    selected = []
    seen: set[str] = set()
    for keyword in keywords:
        for app in snapshot.applications:
            label = _app_label(app.name, app.version)
            key = label.casefold()
            if keyword in app.name.casefold() and key not in seen:
                selected.append(label)
                seen.add(key)
                break
    return ", ".join(selected[:12]) if selected else "none detected"


def _app_label(name: Any, version: Any) -> str:
    if version in (None, ""):
        return _english_text(name)
    if str(version).casefold() in str(name).casefold():
        return _english_text(name)
    return f"{_english_text(name)} {version}"


def _format_bytes(value: Any) -> str:
    if value is None:
        return "unknown"
    size = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit in {"GiB", "TiB"}:
                return f"{size:.1f} {unit}"
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def _format_mib(value: Any) -> str:
    if value is None:
        return "unknown"
    try:
        gib = float(value) / 1024.0
        return f"{gib:.1f} GiB"
    except (TypeError, ValueError):
        return str(value)


def _optional_mib(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return _format_mib(value)


def _optional_pair(label: str, value: Any) -> str | None:
    if value is None or value == "":
        return None
    return f"{label}: {value}"


def _optional_hz(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return f"{value} Hz"


def _optional_mt_s(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return f"{value} MT/s"


def _optional_mhz(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return f"{value} MHz"


def _optional_kib(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return f"{value} KiB"


def _optional_watts(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"{float(value):.2f} W"
    except (TypeError, ValueError):
        return str(value)


def _optional_percent(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return str(value)


def _pcie_link_label(runtime: dict[str, Any]) -> str | None:
    current = runtime.get("pcie_link_gen_current")
    maximum = runtime.get("pcie_link_gen_max")
    if current not in (None, "") and maximum not in (None, ""):
        return f"Gen{current} / Max Gen{maximum}"
    if current not in (None, ""):
        return f"Gen{current}"
    return None


def _chassis_label(chassis: dict[str, Any]) -> str:
    types = [item for item in _list(chassis, "types") if isinstance(item, int)]
    if not types:
        return "unknown"
    primary = types[0]
    base = CHASSIS_LABELS.get(primary, f"Type {primary}")
    return f"{base}-class (ChassisTypes={{{', '.join(str(item) for item in types)}}})"


def _volume_summary(total_bytes: Any, free_bytes: Any) -> str:
    return f"{_format_bytes(total_bytes)} total / {_format_bytes(free_bytes)} free"


def _list_label(values: list[Any], *, limit: int) -> str:
    labels = [_english_text(item).strip() for item in values if str(item).strip()]
    if not labels:
        return "unknown"
    suffix = "" if len(labels) <= limit else f", +{len(labels) - limit} more"
    return f"{', '.join(labels[:limit])}{suffix}"


def _bool_label(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "unknown"


def _join_values(parts: list[str | None]) -> str:
    values = [part for part in parts if part]
    return " / ".join(values) if values else "unknown"


def _english_text(value: Any) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "イーサネット": "Ethernet",
        "ネットワーク接続": "Network Connection",
        "高品位オーディオ デバイス": "High Definition Audio Device",
        "High Definition Audio デバイス": "High Definition Audio Device",
        "USB オーディオ": "USB Audio",
        "オーディオ": "Audio",
        "デバイス": "Device",
        "接続済み": "Connected",
        "切断済み": "Disconnected",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _normalize_architecture(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    replacements = {
        "64 ビット": "64-bit",
        "32 ビット": "32-bit",
        "64-bit": "64-bit",
        "32-bit": "32-bit",
    }
    return replacements.get(text, text)


def _join_non_empty(*parts: Any, separator: str = " ") -> str:
    values = [str(part) for part in parts if part not in (None, "")]
    return separator.join(values) if values else "unknown"


def _or(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _dict(container: dict[str, Any], key: str) -> dict[str, Any]:
    value = container.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _list(container: dict[str, Any], key: str) -> list[Any]:
    value = container.get(key)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if value is not None:
        return [value]
    return []
