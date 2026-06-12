from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from timeline_for_pc_info.runner import run_capture


EXPECTED_RUN_FILES = {
    "request.json",
    "status.json",
    "result.json",
    "manifest.json",
    "snapshot.json",
    "snapshot_redacted.json",
    "report.md",
    "export",
}

REQUIRED_MARKDOWN_SNIPPETS = (
    "Captured at:",
    "## System",
    "PC name:",
    "BIOS release date:",
    "## OS",
    "Hotfixes:",
    "## CPU / Memory / GPU",
    "CPU details:",
    "Memory layout:",
    "Memory slots:",
    "Configuration notes:",
    "GPU runtime:",
    "## Display",
    "## Storage",
    "Total physical capacity:",
    "## Network / WSL",
    "## Audio / Virtualization",
    "Hypervisor present:",
    "## Installed Apps",
    "Installed apps count:",
)

FORBIDDEN_MARKDOWN_SNIPPETS = (
    "## 差分",
    "## ネットワーク / WSL",
    "初回スナップショット",
    "Manual note:",
)


@dataclass(frozen=True)
class SmokeResult:
    ok: bool
    run_dir: Path
    export_path: Path | None
    issues: tuple[str, ...]


def run_smoke_test(
    *,
    output_root: Path,
    live: bool,
    redaction_profile: str,
) -> SmokeResult:
    run_dir = run_capture(
        output_root=output_root,
        mock=not live,
        mock_profile="baseline",
        redaction_profile=redaction_profile,
    )
    export_path, issues = validate_run_dir(
        run_dir=run_dir,
        expected_capture_mode="windows" if live else "mock",
        redaction_profile=redaction_profile,
    )
    return SmokeResult(
        ok=not issues,
        run_dir=run_dir,
        export_path=export_path,
        issues=tuple(issues),
    )


def validate_run_dir(
    *,
    run_dir: Path,
    expected_capture_mode: str,
    redaction_profile: str,
) -> tuple[Path | None, list[str]]:
    issues: list[str] = []
    if not run_dir.exists():
        return None, [f"Run directory does not exist: {run_dir}"]

    actual_files = {path.name for path in run_dir.iterdir()}
    missing_files = sorted(EXPECTED_RUN_FILES - actual_files)
    if missing_files:
        issues.append(f"Missing expected files: {', '.join(missing_files)}")

    if (run_dir / "diff.json").exists():
        issues.append("Unexpected diff.json was created.")

    export_files = sorted((run_dir / "export").glob("*.md")) if (run_dir / "export").exists() else []
    if len(export_files) != 1:
        issues.append(f"Expected exactly one export markdown file, found {len(export_files)}.")
        export_path = export_files[0] if export_files else None
    else:
        export_path = export_files[0]
        if not re.fullmatch(r"\d{12}\.md", export_path.name):
            issues.append(f"Export filename is not YYYYMMDDHHMM.md: {export_path.name}")

    result = _read_json(run_dir / "result.json", issues)
    request = _read_json(run_dir / "request.json", issues)
    manifest = _read_json(run_dir / "manifest.json", issues)
    snapshot_redacted = _read_json(run_dir / "snapshot_redacted.json", issues)

    if isinstance(request, dict) and request.get("capture_mode") != expected_capture_mode:
        issues.append(
            f"Unexpected capture mode: expected {expected_capture_mode}, got {request.get('capture_mode')}"
        )

    if isinstance(result, dict):
        if "diff_path" in result:
            issues.append("result.json still contains diff_path.")
        if "previous_snapshot_path" in result:
            issues.append("result.json still contains previous_snapshot_path.")
        if export_path is not None and Path(str(result.get("export_markdown_path"))) != export_path:
            issues.append("result.json export_markdown_path does not match the export file.")
        _validate_timeline_artifacts(result=result, issues=issues)

    if isinstance(manifest, dict):
        files = manifest.get("files")
        if isinstance(files, list) and any(str(item).endswith("diff.json") for item in files):
            issues.append("manifest.json still lists diff.json.")

    if redaction_profile == "llm_safe" and isinstance(snapshot_redacted, dict):
        host = snapshot_redacted.get("host")
        if not isinstance(host, dict) or host.get("name") != "[redacted-host]":
            issues.append("snapshot_redacted.json does not redact the host name.")
        details = snapshot_redacted.get("details")
        platform = details.get("platform") if isinstance(details, dict) else None
        if isinstance(platform, dict) and platform.get("computer_name") != "[redacted-host]":
            issues.append("snapshot_redacted.json does not redact details.platform.computer_name.")

    _validate_markdown(run_dir=run_dir, export_path=export_path, issues=issues)
    return export_path, issues


def _validate_markdown(*, run_dir: Path, export_path: Path | None, issues: list[str]) -> None:
    report_path = run_dir / "report.md"
    if not report_path.exists():
        return
    report_markdown = report_path.read_text(encoding="utf-8")
    export_markdown = export_path.read_text(encoding="utf-8") if export_path and export_path.exists() else None

    if export_markdown is not None and export_markdown != report_markdown:
        issues.append("report.md and export markdown do not match.")

    for snippet in REQUIRED_MARKDOWN_SNIPPETS:
        if snippet not in report_markdown:
            issues.append(f"Markdown is missing required text: {snippet}")
    for snippet in FORBIDDEN_MARKDOWN_SNIPPETS:
        if snippet in report_markdown:
            issues.append(f"Markdown still contains forbidden text: {snippet}")


def _validate_timeline_artifacts(*, result: dict[str, Any], issues: list[str]) -> None:
    artifacts = result.get("timeline_artifacts")
    if not isinstance(artifacts, dict):
        issues.append("result.json is missing timeline_artifacts.")
        return

    status = artifacts.get("update_status")
    if status not in {"first_seen", "changed", "unchanged"}:
        issues.append(f"Unexpected timeline update_status: {status}")

    for key in (
        "timeline_path",
        "convert_info_path",
        "items_index_path",
        "events_index_path",
        "root_manifest_path",
    ):
        raw_path = artifacts.get(key)
        if not raw_path or not Path(str(raw_path)).exists():
            issues.append(f"Timeline artifact does not exist: {key}")


def _read_json(path: Path, issues: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(f"Invalid JSON in {path.name}: {exc}")
        return None
    if not isinstance(raw, dict):
        issues.append(f"Unexpected JSON shape in {path.name}.")
        return None
    return raw
