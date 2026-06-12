from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from timeline_for_pc_info.mock_data import get_mock_snapshot
from timeline_for_pc_info.models import Snapshot


class CollectorError(RuntimeError):
    """Raised when the collector cannot produce a snapshot."""


def collect_snapshot(*, mock: bool, mock_profile: str) -> Snapshot:
    if mock:
        return get_mock_snapshot(mock_profile)
    return _collect_from_windows()


def _collect_from_windows() -> Snapshot:
    powershell = _resolve_powershell()
    script_path = Path(__file__).with_name("powershell").joinpath("collect_snapshot.ps1")

    completed = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "collector failed"
        raise CollectorError(message)

    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CollectorError("collector returned invalid JSON") from exc

    if not isinstance(raw, dict):
        raise CollectorError("collector returned an unexpected JSON shape")

    normalized = _normalize_raw_snapshot(raw)
    _augment_runtime_details(normalized)
    return Snapshot.from_dict(normalized)


def _resolve_powershell() -> str:
    for candidate in ("powershell.exe", "pwsh", "powershell"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise CollectorError("PowerShell was not found in PATH")


def _normalize_raw_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    applications = sorted(
        (
            {
                "name": str(item.get("name", "Unknown App")).strip(),
                "version": _clean(item.get("version")),
                "publisher": _clean(item.get("publisher")),
            }
            for item in _list_of_dicts(raw.get("applications"))
            if str(item.get("name", "")).strip()
        ),
        key=lambda item: (
            item["name"].casefold(),
            (item.get("version") or "").casefold(),
            (item.get("publisher") or "").casefold(),
        ),
    )

    return {
        "schema_version": 1,
        "captured_at_utc": str(raw.get("captured_at_utc", "")),
        "capture_mode": "windows",
        "os": {
            "product_name": str(raw.get("os", {}).get("product_name", "Unknown Windows")),
            "version": _clean(raw.get("os", {}).get("version")),
            "build_number": _clean(raw.get("os", {}).get("build_number")),
            "architecture": _clean(raw.get("os", {}).get("architecture")),
        },
        "host": {
            "name": _clean(raw.get("host", {}).get("name")),
            "manufacturer": _clean(raw.get("host", {}).get("manufacturer")),
            "model": _clean(raw.get("host", {}).get("model")),
            "system_type": _clean(raw.get("host", {}).get("system_type")),
            "total_memory_bytes": _int_or_none(raw.get("host", {}).get("total_memory_bytes")),
            "motherboard": {
                "manufacturer": _clean(raw.get("host", {}).get("motherboard", {}).get("manufacturer")),
                "product": _clean(raw.get("host", {}).get("motherboard", {}).get("product")),
            },
        },
        "processors": sorted(
            (
                {
                    "name": str(item.get("name", "Unknown CPU")).strip(),
                    "cores": _int_or_none(item.get("cores")),
                    "logical_processors": _int_or_none(item.get("logical_processors")),
                    "max_clock_mhz": _int_or_none(item.get("max_clock_mhz")),
                }
                for item in _list_of_dicts(raw.get("processors"))
                if str(item.get("name", "")).strip()
            ),
            key=lambda item: item["name"].casefold(),
        ),
        "gpus": sorted(
            (
                {
                    "name": str(item.get("name", "Unknown GPU")).strip(),
                    "driver_version": _clean(item.get("driver_version")),
                    "adapter_ram_bytes": _int_or_none(item.get("adapter_ram_bytes")),
                }
                for item in _list_of_dicts(raw.get("gpus"))
                if str(item.get("name", "")).strip()
            ),
            key=lambda item: item["name"].casefold(),
        ),
        "physical_disks": sorted(
            (
                {
                    "name": str(item.get("name", "Unknown Disk")).strip(),
                    "media_type": _clean(item.get("media_type")),
                    "bus_type": _clean(item.get("bus_type")),
                    "size_bytes": _int_or_none(item.get("size_bytes")),
                    "health_status": _clean(item.get("health_status")),
                }
                for item in _list_of_dicts(raw.get("physical_disks"))
                if str(item.get("name", "")).strip()
            ),
            key=lambda item: (item["name"].casefold(), item.get("size_bytes") or 0),
        ),
        "volumes": sorted(
            (
                {
                    "name": str(item.get("name", "Unknown Volume")).strip(),
                    "root": _clean(item.get("root")),
                    "used_bytes": _int_or_none(item.get("used_bytes")),
                    "free_bytes": _int_or_none(item.get("free_bytes")),
                    "total_bytes": _int_or_none(item.get("total_bytes")),
                }
                for item in _list_of_dicts(raw.get("volumes"))
                if str(item.get("name", "")).strip()
            ),
            key=lambda item: item["name"].casefold(),
        ),
        "applications": _dedupe_applications(applications),
        "details": _dict_or_empty(raw.get("details")),
    }


def _augment_runtime_details(snapshot: dict[str, Any]) -> None:
    details = _dict_or_empty(snapshot.get("details"))
    snapshot["details"] = details

    gpu_runtime = _read_nvidia_runtime()
    if gpu_runtime:
        details["gpu_runtime"] = gpu_runtime

    wsl_details = _read_wsl_details()
    if wsl_details:
        current_wsl = _dict_or_empty(details.get("wsl"))
        current_wsl.update(wsl_details)
        details["wsl"] = current_wsl

    cpu_details = _dict_or_empty(details.get("cpu_details"))
    if not cpu_details.get("physical_packages") and snapshot.get("processors"):
        cpu_details["physical_packages"] = 1
    details["cpu_details"] = cpu_details

    memory_details = _dict_or_empty(details.get("memory_details"))
    max_capacity_bytes = _int_or_none(memory_details.get("max_capacity_bytes"))
    host_total_memory = _int_or_none(_dict_or_empty(snapshot.get("host")).get("total_memory_bytes"))
    if (
        max_capacity_bytes is not None
        and host_total_memory is not None
        and max_capacity_bytes < host_total_memory
        and max_capacity_bytes * 1024 >= host_total_memory
    ):
        memory_details["max_capacity_bytes"] = max_capacity_bytes * 1024
    details["memory_details"] = memory_details


def _read_nvidia_runtime() -> list[dict[str, Any]]:
    cmd = shutil.which("cmd.exe")
    if not cmd:
        return []

    completed = subprocess.run(
        [
            cmd,
            "/c",
            "nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,memory.free,temperature.gpu,power.draw,power.limit,fan.speed,clocks.gr,clocks.mem,vbios_version,pci.bus_id,pcie.link.gen.current,pcie.link.gen.max --format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
    )
    text = _decode_command_output(completed.stdout or completed.stderr)
    if completed.returncode != 0 or not text.strip():
        return []

    items: list[dict[str, Any]] = []
    for line in text.splitlines():
        cleaned = line.replace("\x00", "").strip()
        if not cleaned or "NVIDIA-SMI" in cleaned:
            continue
        parts = [part.strip() for part in cleaned.split(",")]
        if len(parts) < 15:
            continue
        items.append(
            {
                "name": parts[0],
                "driver_version_display": parts[1] or None,
                "vram_total_mib": _int_or_none(parts[2]),
                "used_vram_mib": _int_or_none(parts[3]),
                "free_vram_mib": _int_or_none(parts[4]),
                "temperature_c": _int_or_none(parts[5]),
                "power_draw_w": _float_or_none(parts[6]),
                "power_limit_w": _float_or_none(parts[7]),
                "fan_percent": _float_or_none(parts[8]),
                "graphics_clock_mhz": _int_or_none(parts[9]),
                "memory_clock_mhz": _int_or_none(parts[10]),
                "vbios_version": parts[11] or None,
                "pci_bus_id": parts[12] or None,
                "pcie_link_gen_current": _int_or_none(parts[13]),
                "pcie_link_gen_max": _int_or_none(parts[14]),
            }
        )
    return items


def _read_wsl_details() -> dict[str, Any]:
    cmd = shutil.which("cmd.exe")
    if not cmd:
        return {}

    status_output = _run_cmd_text([cmd, "/c", "wsl.exe --status"])
    list_output = _run_cmd_text([cmd, "/c", "wsl.exe -l -v"])

    default_distribution = _match_first(
        status_output,
        (
            r"Default Distribution:\s*(.+)",
            r"既定のディストリビューション:\s*(.+)",
        ),
    )
    default_version = _int_or_none(
        _match_first(
            status_output,
            (
                r"Default Version:\s*(\d+)",
                r"既定のバージョン:\s*(\d+)",
            ),
        )
    )
    kernel = _match_first(
        status_output,
        (
            r"Kernel version:\s*(.+)",
            r"カーネル バージョン:\s*(.+)",
        ),
    )

    distributions: list[dict[str, Any]] = []
    running_distributions: list[str] = []
    for raw_line in list_output.splitlines():
        line = raw_line.replace("\x00", "").strip()
        if not line or "NAME" in line and "VERSION" in line:
            continue
        line = line.lstrip("*").strip()
        columns = re.split(r"\s{2,}", line)
        if len(columns) < 3:
            continue
        entry = {
            "name": columns[0].strip(),
            "state": columns[1].strip(),
            "version": _int_or_none(columns[2].strip()),
        }
        distributions.append(entry)
        if entry["state"].casefold() == "running":
            running_distributions.append(entry["name"])

    linux_release = None
    if default_distribution:
        os_release_output = _run_cmd_text(
            [cmd, "/c", f"wsl.exe -d {default_distribution} cat /etc/os-release"]
        )
        match = re.search(r'^PRETTY_NAME="?(.+?)"?$', os_release_output, re.MULTILINE)
        if match:
            linux_release = match.group(1).strip()
        kernel_output = _run_cmd_text([cmd, "/c", f"wsl.exe -d {default_distribution} uname -r"])
        kernel_lines = [line.replace("\x00", "").strip() for line in kernel_output.splitlines() if line.strip()]
        if kernel is None and kernel_lines:
            kernel = kernel_lines[0]

    result = {
        "default_distribution": default_distribution,
        "default_version": default_version,
        "running_distributions": running_distributions,
        "distributions": distributions,
        "linux_release": linux_release,
        "kernel": kernel,
    }
    return {key: value for key, value in result.items() if value not in (None, [], {})}


def _run_cmd_text(args: list[str]) -> str:
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
    )
    return _decode_command_output(completed.stdout or completed.stderr)


def _decode_command_output(data: bytes) -> str:
    if not data:
        return ""
    encodings = ["utf-8-sig", "utf-16le", "utf-16", "cp932", "latin-1"]
    if b"\x00" in data:
        encodings = ["utf-16le", "utf-16", "utf-8-sig", "cp932", "latin-1"]
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _match_first(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _dedupe_applications(applications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in applications:
        key = (
            item["name"].casefold(),
            (item.get("version") or "").casefold(),
            (item.get("publisher") or "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
