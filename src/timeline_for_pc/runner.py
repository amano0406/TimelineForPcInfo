from __future__ import annotations

import json
import os
import secrets
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from timeline_for_pc.bundle import write_export_report
from timeline_for_pc.collector import collect_snapshot
from timeline_for_pc.redaction import redact_snapshot
from timeline_for_pc.render import render_report
from timeline_for_pc.timeline_store import write_timeline_artifacts


def run_capture(
    *,
    output_root: Path,
    mock: bool,
    mock_profile: str,
    redaction_profile: str,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = _new_run_id()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    started_at_utc = _utc_now()
    _write_json(
        run_dir / "request.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "created_at_utc": started_at_utc,
            "capture_mode": "mock" if mock else "windows",
            "mock_profile": mock_profile if mock else None,
            "redaction_profile": redaction_profile,
            "output_root": str(output_root),
        },
    )
    _write_json(
        run_dir / "status.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "state": "running",
            "current_stage": "collect_snapshot",
            "message": "Collecting machine snapshot.",
            "started_at_utc": started_at_utc,
            "updated_at_utc": started_at_utc,
            "completed_at_utc": None,
        },
    )

    current_snapshot = collect_snapshot(mock=mock, mock_profile=mock_profile)
    redacted_snapshot = redact_snapshot(current_snapshot, redaction_profile)
    report_markdown = render_report(redacted_snapshot)

    _write_json(run_dir / "snapshot.json", current_snapshot.to_dict())
    _write_json(run_dir / "snapshot_redacted.json", redacted_snapshot.to_dict())
    (run_dir / "report.md").write_text(report_markdown, encoding="utf-8")
    export_report_path = write_export_report(
        run_dir=run_dir,
        snapshot_redacted=redacted_snapshot,
        report_markdown=report_markdown,
    )

    completed_at_utc = _utc_now()
    timeline_artifacts = write_timeline_artifacts(
        output_root=output_root,
        run_dir=run_dir,
        run_id=run_id,
        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,
        snapshot=current_snapshot,
        snapshot_redacted=redacted_snapshot,
        capture_mode="mock" if mock else "windows",
        redaction_profile=redaction_profile,
        report_path=run_dir / "report.md",
        export_report_path=export_report_path,
    )

    _write_json(
        run_dir / "manifest.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "files": [
                "request.json",
                "status.json",
                "result.json",
                "manifest.json",
                "snapshot.json",
                "snapshot_redacted.json",
                "report.md",
                str(export_report_path.relative_to(run_dir)),
            ],
            "redaction_profile": redaction_profile,
            "timeline_artifacts": _timeline_artifacts_payload(timeline_artifacts),
        },
    )

    _write_json(
        run_dir / "result.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "state": "completed",
            "run_dir": str(run_dir),
            "snapshot_path": str(run_dir / "snapshot.json"),
            "report_path": str(run_dir / "report.md"),
            "snapshot_redacted_path": str(run_dir / "snapshot_redacted.json"),
            "export_markdown_path": str(export_report_path),
            "timeline_artifacts": _timeline_artifacts_payload(timeline_artifacts),
            "completed_at_utc": completed_at_utc,
        },
    )
    _write_json(
        run_dir / "status.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "state": "completed",
            "current_stage": "completed",
            "message": "Capture completed.",
            "started_at_utc": started_at_utc,
            "updated_at_utc": completed_at_utc,
            "completed_at_utc": completed_at_utc,
        },
    )

    return run_dir


def default_output_root() -> Path:
    if os.name == "nt":
        return Path("C:/apps/Timeline/data/to_text/pc")
    if Path("/mnt/c").exists():
        return Path("/mnt/c/apps/Timeline/data/to_text/pc")

    candidates = (
        Path.home() / "Codex" / "workspaces" / "TimelineForPC",
        Path.cwd() / "TimelineForPC-runs",
    )
    for candidate in candidates:
        if candidate.parent.exists():
            return candidate
    return candidates[-1]


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"run-{stamp}-{secrets.token_hex(4)}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _timeline_artifacts_payload(artifacts: Any) -> dict[str, Any]:
    return {
        "item_id": artifacts.item_id,
        "update_status": artifacts.update_status,
        "event_id": artifacts.event_id,
        "snapshot_fingerprint": artifacts.snapshot_fingerprint,
        "previous_snapshot_fingerprint": artifacts.previous_snapshot_fingerprint,
        "item_dir": str(artifacts.item_dir),
        "timeline_path": str(artifacts.timeline_path),
        "convert_info_path": str(artifacts.convert_info_path),
        "items_index_path": str(artifacts.items_index_path),
        "events_index_path": str(artifacts.events_index_path),
        "root_manifest_path": str(artifacts.root_manifest_path),
    }
