from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProcessorInfo:
    name: str
    cores: int | None = None
    logical_processors: int | None = None
    max_clock_mhz: int | None = None


@dataclass(frozen=True)
class GpuInfo:
    name: str
    driver_version: str | None = None
    adapter_ram_bytes: int | None = None


@dataclass(frozen=True)
class MotherboardInfo:
    manufacturer: str | None = None
    product: str | None = None


@dataclass(frozen=True)
class PhysicalDiskInfo:
    name: str
    media_type: str | None = None
    bus_type: str | None = None
    size_bytes: int | None = None
    health_status: str | None = None


@dataclass(frozen=True)
class VolumeInfo:
    name: str
    root: str | None = None
    used_bytes: int | None = None
    free_bytes: int | None = None
    total_bytes: int | None = None


@dataclass(frozen=True)
class ApplicationInfo:
    name: str
    version: str | None = None
    publisher: str | None = None


@dataclass(frozen=True)
class OsInfo:
    product_name: str
    version: str | None = None
    build_number: str | None = None
    architecture: str | None = None


@dataclass(frozen=True)
class HostInfo:
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    system_type: str | None = None
    total_memory_bytes: int | None = None
    motherboard: MotherboardInfo | None = None


@dataclass(frozen=True)
class Snapshot:
    schema_version: int
    captured_at_utc: str
    capture_mode: str
    os: OsInfo
    host: HostInfo
    processors: tuple[ProcessorInfo, ...]
    gpus: tuple[GpuInfo, ...]
    physical_disks: tuple[PhysicalDiskInfo, ...]
    volumes: tuple[VolumeInfo, ...]
    applications: tuple[ApplicationInfo, ...]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Snapshot":
        host_raw = raw.get("host", {})
        motherboard_raw = host_raw.get("motherboard")
        motherboard = None
        if isinstance(motherboard_raw, dict):
            motherboard = MotherboardInfo(
                manufacturer=_str_or_none(motherboard_raw.get("manufacturer")),
                product=_str_or_none(motherboard_raw.get("product")),
            )

        return cls(
            schema_version=_int_or_default(raw.get("schema_version"), SCHEMA_VERSION),
            captured_at_utc=str(raw.get("captured_at_utc", "")),
            capture_mode=str(raw.get("capture_mode", "unknown")),
            os=OsInfo(
                product_name=str(raw.get("os", {}).get("product_name", "Unknown Windows")),
                version=_str_or_none(raw.get("os", {}).get("version")),
                build_number=_str_or_none(raw.get("os", {}).get("build_number")),
                architecture=_str_or_none(raw.get("os", {}).get("architecture")),
            ),
            host=HostInfo(
                name=_str_or_none(host_raw.get("name")),
                manufacturer=_str_or_none(host_raw.get("manufacturer")),
                model=_str_or_none(host_raw.get("model")),
                system_type=_str_or_none(host_raw.get("system_type")),
                total_memory_bytes=_int_or_none(host_raw.get("total_memory_bytes")),
                motherboard=motherboard,
            ),
            processors=tuple(
                ProcessorInfo(
                    name=str(item.get("name", "Unknown CPU")),
                    cores=_int_or_none(item.get("cores")),
                    logical_processors=_int_or_none(item.get("logical_processors")),
                    max_clock_mhz=_int_or_none(item.get("max_clock_mhz")),
                )
                for item in _list_of_dicts(raw.get("processors"))
            ),
            gpus=tuple(
                GpuInfo(
                    name=str(item.get("name", "Unknown GPU")),
                    driver_version=_str_or_none(item.get("driver_version")),
                    adapter_ram_bytes=_int_or_none(item.get("adapter_ram_bytes")),
                )
                for item in _list_of_dicts(raw.get("gpus"))
            ),
            physical_disks=tuple(
                PhysicalDiskInfo(
                    name=str(item.get("name", "Unknown Disk")),
                    media_type=_str_or_none(item.get("media_type")),
                    bus_type=_str_or_none(item.get("bus_type")),
                    size_bytes=_int_or_none(item.get("size_bytes")),
                    health_status=_str_or_none(item.get("health_status")),
                )
                for item in _list_of_dicts(raw.get("physical_disks"))
            ),
            volumes=tuple(
                VolumeInfo(
                    name=str(item.get("name", "Unknown Volume")),
                    root=_str_or_none(item.get("root")),
                    used_bytes=_int_or_none(item.get("used_bytes")),
                    free_bytes=_int_or_none(item.get("free_bytes")),
                    total_bytes=_int_or_none(item.get("total_bytes")),
                )
                for item in _list_of_dicts(raw.get("volumes"))
            ),
            applications=tuple(
                ApplicationInfo(
                    name=str(item.get("name", "Unknown App")),
                    version=_str_or_none(item.get("version")),
                    publisher=_str_or_none(item.get("publisher")),
                )
                for item in _list_of_dicts(raw.get("applications"))
            ),
            details=_dict_or_empty(raw.get("details")),
        )


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_default(value: Any, default: int) -> int:
    converted = _int_or_none(value)
    return default if converted is None else converted


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
