from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from timeline_for_pc_info.models import Snapshot


FINGERPRINT_IGNORED_FIELDS = (
    "captured_at_utc",
    "host.name",
    "details.platform.computer_name",
    "details.platform.uuid",
    "volumes.used_bytes",
    "volumes.free_bytes",
    "details.gpu_runtime",
    "details.os_details.last_boot_local",
    "details.wsl.running_distributions",
    "network adapter IP/runtime-only fields",
)


@dataclass(frozen=True)
class TimelineArtifacts:
    item_id: str
    item_dir: Path
    timeline_path: Path
    convert_info_path: Path
    items_index_path: Path
    events_index_path: Path
    root_manifest_path: Path
    update_status: str
    event_id: str
    snapshot_fingerprint: str
    previous_snapshot_fingerprint: str | None


class TimelineStoreError(RuntimeError):
    """Raised when an existing timeline store cannot be safely updated."""


def write_timeline_artifacts(
    *,
    output_root: Path,
    run_dir: Path,
    run_id: str,
    started_at_utc: str,
    completed_at_utc: str,
    snapshot: Snapshot,
    snapshot_redacted: Snapshot,
    capture_mode: str,
    redaction_profile: str,
    report_path: Path,
    export_report_path: Path,
) -> TimelineArtifacts:
    item_id = pc_item_id(snapshot)
    item_dir = output_root / "items" / item_id
    item_dir.mkdir(parents=True, exist_ok=True)

    timeline_path = item_dir / "timeline.json"
    convert_info_path = item_dir / "convert_info.json"
    items_index_path = output_root / "items.jsonl"
    events_index_path = output_root / "events.jsonl"
    root_manifest_path = output_root / "manifest.json"

    snapshot_fingerprint = compute_snapshot_fingerprint(snapshot_redacted)
    previous_convert_info = _read_optional_json_object(convert_info_path)
    previous_fingerprint = _string_or_none(previous_convert_info.get("snapshot_fingerprint"))

    if previous_fingerprint is None:
        update_status = "first_seen"
    elif previous_fingerprint == snapshot_fingerprint:
        update_status = "unchanged"
    else:
        update_status = "changed"

    event_id = _event_id(run_id=run_id, snapshot_fingerprint=snapshot_fingerprint)
    event = {
        "schema_version": 1,
        "event_id": event_id,
        "event_type": "pc_snapshot_captured",
        "item_id": item_id,
        "occurred_at_utc": snapshot_redacted.captured_at_utc,
        "recorded_at_utc": completed_at_utc,
        "run_id": run_id,
        "capture_mode": capture_mode,
        "update_status": update_status,
        "summary": _event_summary(snapshot_redacted=snapshot_redacted, update_status=update_status),
        "snapshot_fingerprint": snapshot_fingerprint,
        "previous_snapshot_fingerprint": previous_fingerprint,
        "artifact_refs": {
            "run_dir": _relative_path(run_dir, output_root),
            "report_md": _relative_path(report_path, output_root),
            "export_md": _relative_path(export_report_path, output_root),
            "snapshot_redacted_json": _relative_path(run_dir / "snapshot_redacted.json", output_root),
        },
    }

    timeline = _load_or_create_timeline(
        timeline_path=timeline_path,
        item_id=item_id,
        created_at_utc=started_at_utc,
    )
    timeline["updated_at_utc"] = completed_at_utc
    timeline["latest_run_id"] = run_id
    timeline["latest_event_id"] = event_id
    timeline["latest_update_status"] = update_status
    timeline["latest_snapshot_fingerprint"] = snapshot_fingerprint
    timeline["events"].append(event)
    _write_json_atomic(timeline_path, timeline)

    convert_info = {
        "schema_version": 1,
        "product": "TimelineForPcInfo",
        "item_id": item_id,
        "item_type": "windows_pc",
        "source_type": "local_windows_host",
        "created_at_utc": previous_convert_info.get("created_at_utc") or started_at_utc,
        "updated_at_utc": completed_at_utc,
        "latest_run_id": run_id,
        "latest_event_id": event_id,
        "update_status": update_status,
        "capture_mode": capture_mode,
        "redaction_profile": redaction_profile,
        "snapshot_fingerprint": snapshot_fingerprint,
        "previous_snapshot_fingerprint": previous_fingerprint,
        "fingerprint_scope": "material_pc_configuration",
        "fingerprint_ignored_fields": list(FINGERPRINT_IGNORED_FIELDS),
        "artifact_refs": event["artifact_refs"],
    }
    _write_json_atomic(convert_info_path, convert_info)

    item_index = {
        "schema_version": 1,
        "item_id": item_id,
        "item_type": "windows_pc",
        "title": "Windows PC snapshot history",
        "updated_at_utc": completed_at_utc,
        "latest_run_id": run_id,
        "latest_event_id": event_id,
        "latest_update_status": update_status,
        "latest_snapshot_fingerprint": snapshot_fingerprint,
        "timeline_path": _relative_path(timeline_path, output_root),
        "convert_info_path": _relative_path(convert_info_path, output_root),
    }
    _write_text_atomic(items_index_path, json.dumps(item_index, ensure_ascii=False, sort_keys=True) + "\n")
    _append_jsonl(events_index_path, event)

    root_manifest = {
        "schema_version": 1,
        "product": "TimelineForPcInfo",
        "updated_at_utc": completed_at_utc,
        "item_count": 1,
        "event_count": len(timeline["events"]),
        "files": [
            _relative_path(items_index_path, output_root),
            _relative_path(events_index_path, output_root),
            _relative_path(timeline_path, output_root),
            _relative_path(convert_info_path, output_root),
        ],
    }
    _write_json_atomic(root_manifest_path, root_manifest)

    return TimelineArtifacts(
        item_id=item_id,
        item_dir=item_dir,
        timeline_path=timeline_path,
        convert_info_path=convert_info_path,
        items_index_path=items_index_path,
        events_index_path=events_index_path,
        root_manifest_path=root_manifest_path,
        update_status=update_status,
        event_id=event_id,
        snapshot_fingerprint=snapshot_fingerprint,
        previous_snapshot_fingerprint=previous_fingerprint,
    )


def pc_item_id(snapshot: Snapshot) -> str:
    identity_parts = []
    platform = snapshot.details.get("platform")
    if isinstance(platform, dict):
        identity_parts.append(_string_or_none(platform.get("uuid")) or "")
        identity_parts.append(_string_or_none(platform.get("computer_name")) or "")
    identity_parts.extend(
        [
            snapshot.host.name or "",
            snapshot.host.manufacturer or "",
            snapshot.host.model or "",
            snapshot.host.motherboard.manufacturer if snapshot.host.motherboard else "",
            snapshot.host.motherboard.product if snapshot.host.motherboard else "",
        ]
    )
    identity = "|".join(part for part in identity_parts if part)
    if not identity:
        identity = "local-windows-pc"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"pc-{digest}"


def compute_snapshot_fingerprint(snapshot: Snapshot) -> str:
    material_snapshot = _material_snapshot(snapshot)
    encoded = json.dumps(material_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _material_snapshot(snapshot: Snapshot) -> dict[str, Any]:
    details = snapshot.details
    return {
        "schema_version": snapshot.schema_version,
        "capture_mode": snapshot.capture_mode,
        "os": snapshot.os.to_dict() if hasattr(snapshot.os, "to_dict") else {
            "product_name": snapshot.os.product_name,
            "version": snapshot.os.version,
            "build_number": snapshot.os.build_number,
            "architecture": snapshot.os.architecture,
        },
        "host": {
            "manufacturer": snapshot.host.manufacturer,
            "model": snapshot.host.model,
            "system_type": snapshot.host.system_type,
            "total_memory_bytes": snapshot.host.total_memory_bytes,
            "motherboard": _clean_json(snapshot.host.motherboard.__dict__ if snapshot.host.motherboard else None),
        },
        "processors": _sorted_clean(
            {
                "name": item.name,
                "cores": item.cores,
                "logical_processors": item.logical_processors,
                "max_clock_mhz": item.max_clock_mhz,
            }
            for item in snapshot.processors
        ),
        "gpus": _sorted_clean(
            {
                "name": item.name,
                "driver_version": item.driver_version,
                "adapter_ram_bytes": item.adapter_ram_bytes,
            }
            for item in snapshot.gpus
        ),
        "physical_disks": _sorted_clean(
            {
                "name": item.name,
                "media_type": item.media_type,
                "bus_type": item.bus_type,
                "size_bytes": item.size_bytes,
                "health_status": item.health_status,
            }
            for item in snapshot.physical_disks
        ),
        "volumes": _sorted_clean(
            {
                "name": item.name,
                "root": item.root,
                "total_bytes": item.total_bytes,
            }
            for item in snapshot.volumes
        ),
        "applications": _sorted_clean(
            {
                "name": item.name,
                "version": item.version,
            }
            for item in snapshot.applications
        ),
        "details": {
            "bios": _clean_json(details.get("bios")),
            "chassis": _clean_json(details.get("chassis")),
            "os_details": _selected_mapping(
                details.get("os_details"),
                (
                    "wmi_product_name",
                    "registry_product_name",
                    "edition_id",
                    "build_label",
                    "install_date_local",
                    "hotfixes",
                    "notes",
                ),
            ),
            "cpu_details": _clean_json(details.get("cpu_details")),
            "memory_details": _clean_json(details.get("memory_details")),
            "display": _clean_json(details.get("display")),
            "storage_details": _clean_json(details.get("storage_details")),
            "network": _material_network(details.get("network")),
            "audio": _clean_json(details.get("audio")),
            "virtualization": _clean_json(details.get("virtualization")),
            "wsl": _selected_mapping(
                details.get("wsl"),
                ("default_distribution", "default_version", "linux_release", "kernel"),
            ),
        },
    }


def _material_network(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    adapters = value.get("adapters")
    if not isinstance(adapters, list):
        return {}
    return {
        "adapters": _sorted_clean(
            {
                "name": item.get("name"),
                "kind": item.get("kind"),
                "link_speed": item.get("link_speed"),
            }
            for item in adapters
            if isinstance(item, dict)
        )
    }


def _event_summary(*, snapshot_redacted: Snapshot, update_status: str) -> str:
    if update_status == "first_seen":
        prefix = "Initial PC configuration snapshot captured."
    elif update_status == "unchanged":
        prefix = "No material PC configuration change detected."
    else:
        prefix = "Material PC configuration change detected."

    gpu_count = len(snapshot_redacted.gpus)
    disk_count = len(snapshot_redacted.physical_disks)
    app_count = len(snapshot_redacted.applications)
    os_build = snapshot_redacted.os.build_number or "unknown build"
    return f"{prefix} OS build {os_build}; GPUs: {gpu_count}; physical disks: {disk_count}; installed apps: {app_count}."


def _load_or_create_timeline(*, timeline_path: Path, item_id: str, created_at_utc: str) -> dict[str, Any]:
    if not timeline_path.exists():
        return {
            "schema_version": 1,
            "item_id": item_id,
            "item_type": "windows_pc",
            "title": "Windows PC snapshot history",
            "created_at_utc": created_at_utc,
            "updated_at_utc": created_at_utc,
            "latest_run_id": None,
            "latest_event_id": None,
            "latest_update_status": None,
            "latest_snapshot_fingerprint": None,
            "events": [],
        }

    raw = _read_json_object(timeline_path)
    events = raw.get("events")
    if not isinstance(events, list):
        raise TimelineStoreError(f"Existing timeline has invalid events shape: {timeline_path}")
    if raw.get("item_id") != item_id:
        raise TimelineStoreError(f"Existing timeline item_id does not match this PC: {timeline_path}")
    return raw


def _event_id(*, run_id: str, snapshot_fingerprint: str) -> str:
    digest = hashlib.sha256(f"{run_id}|{snapshot_fingerprint}".encode("utf-8")).hexdigest()[:12]
    return f"evt-{digest}"


def _selected_mapping(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: _clean_json(value.get(key)) for key in keys if key in value}


def _sorted_clean(items: Any) -> list[Any]:
    cleaned = [_clean_json(item) for item in items]
    return sorted(cleaned, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))


def _clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_json(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_clean_json(item) for item in value]
    return value


def _read_optional_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json_object(path)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TimelineStoreError(f"Invalid JSON in existing timeline store file: {path}") from exc
    if not isinstance(raw, dict):
        raise TimelineStoreError(f"Timeline store file must contain a JSON object: {path}")
    return raw


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
