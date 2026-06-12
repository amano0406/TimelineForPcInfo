from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DownloadResult:
    archive_path: Path
    item_count: int
    event_count: int


def list_items(*, output_root: Path, page: int, page_size: int) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, page_size)
    items = _discover_items(output_root)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return {
        "schema_version": 1,
        "ok": True,
        "output_root": str(output_root),
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "returned": len(page_items),
            "has_next": end < total,
        },
        "item_count": total,
        "items": page_items,
    }


def download_items(
    *,
    output_root: Path,
    output_path: Path | None,
    to_dir: Path | None,
    overwrite: bool,
    item_ids: list[str] | None = None,
) -> DownloadResult:
    archive_path = _resolve_archive_path(
        output_root=output_root,
        output_path=output_path,
        to_dir=to_dir,
    )
    if archive_path.exists() and not overwrite:
        raise FileExistsError(f"Archive already exists: {archive_path}")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()

    item_dirs = _selected_item_dirs(output_root=output_root, item_ids=item_ids)
    event_count = 0
    for item_dir in item_dirs:
        timeline = _read_optional_json_object(item_dir / "timeline.json")
        events = timeline.get("events")
        if isinstance(events, list):
            event_count += len(events)

    created_at = _utc_now()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "artifact_type": "timeline_for_pc_info_items_download",
                    "product": "TimelineForPcInfo",
                    "created_at_utc": created_at,
                    "item_count": len(item_dirs),
                    "event_count": event_count,
                    "files": {
                        "items": "items.jsonl",
                        "events": "events.jsonl",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        archive.writestr(
            "README.md",
            "\n".join(
                [
                    "# TimelineForPcInfo Download Archive",
                    "",
                    "This ZIP contains TimelineForPcInfo item artifacts for Timeline ingestion.",
                    "",
                    "- items/<pc-id>/timeline.json: PC timeline events.",
                    "- items/<pc-id>/convert_info.json: latest conversion and fingerprint metadata.",
                    "- items.jsonl: one row per PC item.",
                    "- events.jsonl: one row per PC capture event.",
                    "",
                ]
            ),
        )

        for root_file_name in ("items.jsonl", "events.jsonl"):
            root_file = output_root / root_file_name
            if root_file.exists():
                archive.write(root_file, root_file_name)

        for item_dir in item_dirs:
            item_id = item_dir.name
            for file_name in ("timeline.json", "convert_info.json"):
                path = item_dir / file_name
                if path.exists():
                    archive.write(path, f"items/{item_id}/{file_name}")

    return DownloadResult(
        archive_path=archive_path,
        item_count=len(item_dirs),
        event_count=event_count,
    )


def download_result_payload(result: DownloadResult) -> dict[str, Any]:
    archive_path = str(result.archive_path)
    return {
        "schema_version": 1,
        "ok": True,
        "archive_path": archive_path,
        "archivePath": archive_path,
        "item_count": result.item_count,
        "event_count": result.event_count,
    }


def _discover_items(output_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item_dir in _item_dirs(output_root):
        timeline_path = item_dir / "timeline.json"
        convert_info_path = item_dir / "convert_info.json"
        timeline = _read_optional_json_object(timeline_path)
        convert_info = _read_optional_json_object(convert_info_path)
        events = timeline.get("events")
        event_count = len(events) if isinstance(events, list) else 0
        item_id = _text(timeline.get("item_id") or convert_info.get("item_id") or item_dir.name)
        items.append(
            {
                "schema_version": 1,
                "item_id": item_id,
                "itemId": item_id,
                "item_type": _text(timeline.get("item_type") or convert_info.get("item_type") or "windows_pc"),
                "title": _text(timeline.get("title") or "Windows PC snapshot history"),
                "created_at_utc": _text(timeline.get("created_at_utc") or convert_info.get("created_at_utc")),
                "updated_at_utc": _text(timeline.get("updated_at_utc") or convert_info.get("updated_at_utc")),
                "event_count": event_count,
                "latest_update_status": _text(
                    timeline.get("latest_update_status") or convert_info.get("update_status")
                ),
                "timeline_path": str(timeline_path),
                "convert_info_path": str(convert_info_path),
            }
        )

    return sorted(items, key=lambda item: (str(item.get("updated_at_utc")), str(item.get("item_id"))), reverse=True)


def _item_dirs(output_root: Path) -> list[Path]:
    items_root = output_root / "items"
    if not items_root.exists():
        return []
    return sorted(
        (
            path
            for path in items_root.iterdir()
            if path.is_dir()
            and (path / "timeline.json").exists()
            and (path / "convert_info.json").exists()
        ),
        key=lambda path: path.name,
    )


def _selected_item_dirs(*, output_root: Path, item_ids: list[str] | None) -> list[Path]:
    item_dirs = _item_dirs(output_root)
    if not item_ids:
        return item_dirs

    requested = []
    for item_id in item_ids:
        if not _safe_id(item_id):
            raise ValueError(f"Unsafe item id: {item_id}")
        requested.append(item_id)

    by_id = {path.name: path for path in item_dirs}
    missing = [item_id for item_id in requested if item_id not in by_id]
    if missing:
        raise FileNotFoundError(f"Item was not found: {', '.join(missing)}")
    return [by_id[item_id] for item_id in requested]


def _resolve_archive_path(*, output_root: Path, output_path: Path | None, to_dir: Path | None) -> Path:
    if output_path is not None:
        return output_path
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    directory = to_dir if to_dir is not None else output_root / "downloads"
    return directory / f"TimelineForPcInfo-items-{stamp}.zip"


def _read_optional_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_id(value: str) -> bool:
    return bool(value) and "/" not in value and "\\" not in value and value not in {".", ".."}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
