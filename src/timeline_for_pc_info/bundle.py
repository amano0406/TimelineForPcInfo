from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

from timeline_for_pc_info.models import Snapshot


def write_export_report(
    *,
    run_dir: Path,
    snapshot_redacted: Snapshot,
    report_markdown: str,
) -> Path:
    export_dir = run_dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    export_path = export_dir / f"{_capture_label(snapshot_redacted)}.md"
    export_path.write_text(report_markdown, encoding="utf-8")
    return export_path


def _capture_label(snapshot: Snapshot) -> str:
    captured_at = datetime.fromisoformat(snapshot.captured_at_utc.replace("Z", "+00:00")).astimezone(UTC)
    return captured_at.strftime("%Y%m%d%H%M")
