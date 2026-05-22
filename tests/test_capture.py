from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from timeline_for_pc import api_server
from timeline_for_pc.api_server import handle_request
from timeline_for_pc.doctor import DoctorCheck
from timeline_for_pc.doctor import DoctorResult
from timeline_for_pc.doctor import format_doctor_result
from timeline_for_pc.doctor import run_doctor
from timeline_for_pc.runner import run_capture
from timeline_for_pc.settings import AppSettings
from timeline_for_pc.settings import SettingsInitResult
from timeline_for_pc.settings import SettingsSaveResult
from timeline_for_pc.settings import init_settings
from timeline_for_pc.settings import load_settings
from timeline_for_pc.settings import save_settings
from timeline_for_pc.smoke import run_smoke_test


def test_mock_capture_creates_expected_files(tmp_path: Path) -> None:
    run_capture(output_root=tmp_path, mock=True, mock_profile="baseline", redaction_profile="llm_safe")

    run_dirs = _run_dirs(tmp_path)
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    expected_files = {
        "request.json",
        "status.json",
        "result.json",
        "manifest.json",
        "snapshot.json",
        "snapshot_redacted.json",
        "report.md",
    }
    assert expected_files.issubset({path.name for path in run_dir.iterdir()})
    export_files = sorted((run_dir / "export").iterdir())
    assert len(export_files) == 1
    assert export_files[0].name == "202604200000.md"

    snapshot = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["capture_mode"] == "mock"
    assert snapshot["os"]["product_name"] == "Windows 10 Pro"
    redacted_snapshot = json.loads((run_dir / "snapshot_redacted.json").read_text(encoding="utf-8"))
    assert redacted_snapshot["host"]["name"] == "[redacted-host]"
    assert redacted_snapshot["applications"][0]["publisher"] is None
    assert redacted_snapshot["details"]["platform"]["computer_name"] == "[redacted-host]"

    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "11th Gen Intel(R) Core(TM) i7-11700" in report
    assert "Captured at:" in report
    assert "## Network / WSL" in report
    assert "## CPU / Memory / GPU" in report
    assert "PC name:" in report
    assert "BIOS release date:" in report
    assert "Hotfixes:" in report
    assert "CPU details:" in report
    assert "Memory layout:" in report
    assert "Memory slots: 2 / 4" in report
    assert "Memory maximum:" in report
    assert "Configuration notes:" in report
    assert "GPU runtime:" in report
    assert "Small system partitions: 2" in report
    assert "Running WSL distros:" in report
    assert "## Audio / Virtualization" in report
    assert "USB Audio 2.0" in report
    assert "USB オーディオ" not in report
    assert "Hypervisor present: Yes" in report
    assert "## Installed Apps" in report
    assert "Installed apps count: 5" in report
    assert "## 差分" not in report
    assert "## ネットワーク / WSL" not in report


def test_second_mock_capture_keeps_same_minimal_output_shape(tmp_path: Path) -> None:
    run_capture(output_root=tmp_path, mock=True, mock_profile="baseline", redaction_profile="llm_safe")
    run_capture(output_root=tmp_path, mock=True, mock_profile="upgraded", redaction_profile="llm_safe")

    run_dirs = _run_dirs(tmp_path)
    second_run = run_dirs[-1]

    assert not (second_run / "diff.json").exists()

    report = (second_run / "report.md").read_text(encoding="utf-8")
    assert "## 差分" not in report
    assert "Docker Desktop 4.41.0" in report
    assert "## Storage" in report
    assert "Total physical capacity:" in report
    assert "total /" in report
    assert "Hotfixes: 3 installed" in report
    assert "Key installed apps:" in report

    result = json.loads((second_run / "result.json").read_text(encoding="utf-8"))
    assert result["timeline_artifacts"]["update_status"] == "changed"
    assert Path(result["timeline_artifacts"]["timeline_path"]).exists()
    assert result["export_markdown_path"].endswith("202605010000.md")
    assert "diff_path" not in result
    assert "previous_snapshot_path" not in result


def test_smoke_test_validates_mock_output(tmp_path: Path) -> None:
    result = run_smoke_test(output_root=tmp_path, live=False, redaction_profile="llm_safe")

    assert result.ok

    run_dirs = _run_dirs(tmp_path)
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert not (run_dir / "diff.json").exists()

    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    export_path = Path(result["export_markdown_path"])
    assert export_path.exists()
    assert export_path.name == "202604200000.md"

    report = (run_dir / "report.md").read_text(encoding="utf-8")
    export_markdown = export_path.read_text(encoding="utf-8")
    assert report == export_markdown
    assert "## System" in export_markdown
    assert "## Network / WSL" in export_markdown
    assert "## Audio / Virtualization" in export_markdown
    assert "## Installed Apps" in export_markdown
    assert "## 差分" not in export_markdown


def test_items_refresh_is_capture_alias_for_timeline_callers(tmp_path: Path) -> None:
    status, _payload = handle_request(
        "POST",
        "/items/refresh",
        {"mock": True, "mockProfile": "baseline", "outputRoot": str(tmp_path)},
    )

    assert status == 200
    run_dirs = _run_dirs(tmp_path)
    assert len(run_dirs) == 1
    result = json.loads((run_dirs[0] / "result.json").read_text(encoding="utf-8"))
    assert result["timeline_artifacts"]["update_status"] == "first_seen"
    assert (tmp_path / "events.jsonl").exists()


def test_items_refresh_json_reports_run_and_timeline_artifacts(tmp_path: Path) -> None:
    status, payload = handle_request(
        "POST",
        "/items/refresh",
        {"mock": True, "mockProfile": "baseline", "outputRoot": str(tmp_path)},
    )

    assert status == 200
    assert payload["ok"]
    assert payload["state"] == "completed"
    assert Path(payload["run_dir"]).exists()
    assert payload["runDir"] == payload["run_dir"]
    assert payload["timeline_artifacts"]["update_status"] == "first_seen"


def test_items_list_reports_timeline_items_as_json(tmp_path: Path) -> None:
    run_capture(output_root=tmp_path, mock=True, mock_profile="baseline", redaction_profile="llm_safe")

    status, payload = handle_request(
        "POST",
        "/items/list",
        {"outputRoot": str(tmp_path), "page": 1, "pageSize": 1},
    )

    assert status == 200
    assert payload["ok"]
    assert payload["pagination"]["total"] == 1
    assert payload["pagination"]["returned"] == 1
    assert payload["item_count"] == 1
    assert payload["items"][0]["item_type"] == "windows_pc"
    assert payload["items"][0]["event_count"] == 1
    assert payload["items"][0]["latest_update_status"] == "first_seen"


def test_items_download_creates_timeline_ingestion_zip(tmp_path: Path) -> None:
    run_capture(output_root=tmp_path, mock=True, mock_profile="baseline", redaction_profile="llm_safe")
    archive_path = tmp_path / "download.zip"
    item_dir = next((tmp_path / "items").iterdir())
    item_id = item_dir.name

    status, payload = handle_request(
        "POST",
        "/items/download",
        {"outputRoot": str(tmp_path), "outputPath": str(archive_path), "itemIds": [item_id]},
    )

    assert status == 200
    assert payload["ok"]
    assert Path(payload["archive_path"]) == archive_path
    assert payload["archivePath"] == str(archive_path)
    assert payload["item_count"] == 1
    assert payload["event_count"] == 1

    with zipfile.ZipFile(archive_path) as archive:
        entries = set(archive.namelist())

    assert "manifest.json" in entries
    assert "items.jsonl" in entries
    assert "events.jsonl" in entries
    assert f"items/{item_id}/timeline.json" in entries
    assert f"items/{item_id}/convert_info.json" in entries


def test_timeline_artifacts_append_first_seen_unchanged_and_changed_events(tmp_path: Path) -> None:
    run_capture(output_root=tmp_path, mock=True, mock_profile="baseline", redaction_profile="llm_safe")
    run_capture(output_root=tmp_path, mock=True, mock_profile="baseline", redaction_profile="llm_safe")
    run_capture(output_root=tmp_path, mock=True, mock_profile="upgraded", redaction_profile="llm_safe")

    item_dirs = sorted((tmp_path / "items").iterdir())
    assert len(item_dirs) == 1
    item_dir = item_dirs[0]

    timeline = json.loads((item_dir / "timeline.json").read_text(encoding="utf-8"))
    convert_info = json.loads((item_dir / "convert_info.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    items = [json.loads(line) for line in (tmp_path / "items.jsonl").read_text(encoding="utf-8").splitlines()]
    root_manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert [event["update_status"] for event in timeline["events"]] == ["first_seen", "unchanged", "changed"]
    assert [event["update_status"] for event in events] == ["first_seen", "unchanged", "changed"]
    assert convert_info["update_status"] == "changed"
    assert convert_info["fingerprint_scope"] == "material_pc_configuration"
    assert "details.gpu_runtime" in convert_info["fingerprint_ignored_fields"]
    assert items[0]["latest_update_status"] == "changed"
    assert root_manifest["event_count"] == 3
    assert not any(path.name == "diff.json" for path in tmp_path.rglob("*"))


def test_doctor_reports_ok_when_required_tools_exist(tmp_path: Path) -> None:
    def resolve_tool(name: str) -> str | None:
        tools = {
            "powershell.exe": "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "cmd.exe": "C:/Windows/System32/cmd.exe",
            "wsl.exe": "C:/Windows/System32/wsl.exe",
        }
        return tools.get(name)

    def command_succeeds(args: list[str]) -> bool:
        return args[-1] == "nvidia-smi"

    result = run_doctor(
        output_root=tmp_path / "TimelineForPC",
        tool_resolver=resolve_tool,
        command_checker=command_succeeds,
        python_version=(3, 11, 9),
    )
    lines = format_doctor_result(result)

    assert result.ok
    assert lines[0] == "OK"
    assert any("[OK][required] PowerShell" in line for line in lines)
    assert any("[OK][optional] nvidia-smi" in line for line in lines)


def test_doctor_accepts_output_root_that_capture_can_create(tmp_path: Path) -> None:
    result = run_doctor(
        output_root=tmp_path / "TimelineData" / "pc",
        tool_resolver=lambda name: f"/bin/{name}" if name in {"powershell.exe", "cmd.exe", "wsl.exe"} else None,
        command_checker=lambda _args: False,
        python_version=(3, 11, 9),
    )
    lines = format_doctor_result(result)

    assert result.ok
    assert any("[OK][required] Output root" in line for line in lines)


def test_doctor_reports_ng_when_required_tools_are_missing(tmp_path: Path) -> None:
    result = run_doctor(
        output_root=tmp_path / "TimelineForPC",
        tool_resolver=lambda _name: None,
        command_checker=lambda _args: False,
        python_version=(3, 10, 0),
    )
    lines = format_doctor_result(result)

    assert not result.ok
    assert lines[0] == "NG"
    assert any("[NG][required] Python" in line for line in lines)
    assert any("[NG][required] PowerShell" in line for line in lines)
    assert any("[WARN][optional] nvidia-smi" in line for line in lines)


def test_doctor_api_action_reports_json(monkeypatch: Any, tmp_path: Path) -> None:
    def fake_run_doctor(*, output_root: Path) -> DoctorResult:
        assert output_root == tmp_path
        return DoctorResult(
            ok=True,
            checks=(
                DoctorCheck("Python", "required", "OK", "3.11.9 is supported."),
                DoctorCheck("PowerShell", "required", "OK", "Found."),
            ),
        )

    monkeypatch.setattr(api_server, "run_doctor", fake_run_doctor)

    status, payload = handle_request("POST", "/doctor", {"outputRoot": str(tmp_path)})

    assert status == 200
    assert payload["ok"]
    assert payload["runtime"]["kind"] == "windows_host"
    assert payload["runtime"]["state"] == "recordable"
    assert payload["checks"][0]["name"] == "Python"


def test_settings_init_creates_settings_json_without_overwriting(tmp_path: Path) -> None:
    example = tmp_path / "settings.example.json"
    example.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "outputRoot": str(tmp_path / "runs"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    first = init_settings(root=tmp_path)
    assert first.created
    assert first.path == tmp_path / "settings.json"
    assert first.path.read_text(encoding="utf-8") == example.read_text(encoding="utf-8")

    first.path.write_text('{"schema_version": 1, "output_root": "custom"}\n', encoding="utf-8")
    second = init_settings(root=tmp_path)

    assert not second.created
    assert second.path.read_text(encoding="utf-8") == '{"schema_version": 1, "output_root": "custom"}\n'


def test_load_settings_reads_local_settings_json(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "outputRoot": str(tmp_path / "custom-output"),
                "runtime": {
                    "instanceName": "test",
                    "apiPort": 19601,
                },
            }
        ),
        encoding="utf-8",
    )

    settings = load_settings(root=tmp_path)

    assert settings.output_root == tmp_path / "custom-output"
    assert settings.instance_name == "test"
    assert settings.redaction_profile == "llm_safe"
    assert settings.mock_profile == "baseline"
    assert settings.api_port == 19601


def test_settings_init_api_action_reports_result(tmp_path: Path, monkeypatch: Any) -> None:
    def fake_init_settings() -> SettingsInitResult:
        return SettingsInitResult(path=tmp_path / "settings.json", created=True)

    monkeypatch.setattr(api_server, "init_settings", fake_init_settings)

    status, payload = handle_request("POST", "/settings/init", {})

    assert status == 200
    assert payload == {
        "schemaVersion": 1,
        "ok": True,
        "settings_path": str(tmp_path / "settings.json"),
        "created": True,
    }


def test_settings_status_api_action_reports_json(monkeypatch: Any, tmp_path: Path) -> None:
    original_load_settings = api_server.load_settings
    monkeypatch.setattr(
        api_server,
        "load_settings",
        lambda: original_load_settings(root=tmp_path),
    )
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "outputRoot": str(tmp_path / "runs"),
            }
        ),
        encoding="utf-8",
    )

    status, payload = handle_request("POST", "/settings/status", {})

    assert status == 200
    assert payload["ok"]
    assert payload["outputRoot"] == str(tmp_path / "runs")
    assert "redaction_profile" not in payload
    assert "mock_profile" not in payload
    assert payload["runtime"]["instanceName"] == "7d3f91ab4e"
    assert payload["runtime"]["apiPort"] == 19600


def test_settings_save_api_action_reports_json(monkeypatch: Any, tmp_path: Path) -> None:
    current = AppSettings(
        output_root=tmp_path / "old-runs",
    )
    saved_path = tmp_path / "settings.json"

    monkeypatch.setattr(api_server, "load_settings", lambda: current)
    monkeypatch.setattr(
        api_server,
        "save_settings",
        lambda **kwargs: SettingsSaveResult(
            path=saved_path,
            settings=AppSettings(
                output_root=kwargs["output_root"],
                instance_name=kwargs["instance_name"],
            ),
        ),
    )

    status, payload = handle_request(
        "POST",
        "/settings/save",
        {
            "outputRoot": str(tmp_path / "new-runs"),
            "instanceName": "test",
        },
    )

    assert status == 200
    assert payload["ok"]
    assert payload["settings_path"] == str(saved_path)
    assert payload["runtime"]["instanceName"] == "test"
    assert payload["outputRoot"] == str(tmp_path / "new-runs")
    assert "redaction_profile" not in payload
    assert "mock_profile" not in payload


def test_save_settings_preserves_unknown_product_specific_values(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "outputRoot": str(tmp_path / "old"),
                "huggingFaceToken": "hf-secret",
                "runtime": {
                    "instanceName": "old-instance",
                    "apiPort": 19600,
                    "extraRuntimeValue": "keep",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = save_settings(
        root=tmp_path,
        output_root=tmp_path / "new",
        instance_name="new-instance",
        api_port=19601,
    )

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert result.settings.instance_name == "new-instance"
    assert list(payload)[:3] == ["schemaVersion", "runtime", "outputRoot"]
    assert list(payload["runtime"])[:2] == ["instanceName", "apiPort"]
    assert "schema_version" not in payload
    assert "instanceName" not in payload
    assert payload["outputRoot"] == str(tmp_path / "new")
    assert payload["huggingFaceToken"] == "hf-secret"
    assert "apiHost" not in payload["runtime"]
    assert payload["runtime"]["instanceName"] == "new-instance"
    assert payload["runtime"]["apiPort"] == 19601
    assert payload["runtime"]["extraRuntimeValue"] == "keep"


def test_api_server_handles_settings_capture_list_and_download(tmp_path: Path, monkeypatch: Any) -> None:
    product_root = tmp_path / "product"
    source_dir = product_root / "src" / "timeline_for_pc"
    source_dir.mkdir(parents=True)
    output_root = tmp_path / "runs"
    settings_path = product_root / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "runtime": {
                    "instanceName": "api-test",
                    "apiPort": 19600,
                },
                "outputRoot": str(output_root),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TIMELINE_FOR_PC_ROOT", str(product_root))

    health_status, health_payload = handle_request("GET", "/health", None)
    assert health_status == 200
    assert health_payload is True

    settings_status, settings_payload = handle_request("POST", "/settings/status", {})
    assert settings_status == 200
    assert settings_payload["outputRoot"] == str(output_root)
    assert settings_payload["runtime"]["instanceName"] == "api-test"

    refresh_status, refresh_payload = handle_request(
        "POST",
        "/items/refresh",
        {
            "mock": True,
            "mockProfile": "baseline",
            "outputRoot": str(output_root),
        },
    )
    assert refresh_status == 200
    assert refresh_payload["ok"]
    assert refresh_payload["state"] == "completed"

    list_status, list_payload = handle_request(
        "POST",
        "/items/list",
        {"outputRoot": str(output_root), "page": 1, "pageSize": 1},
    )
    assert list_status == 200
    assert list_payload["item_count"] == 1
    item_id = list_payload["items"][0]["item_id"]

    download_status, download_payload = handle_request(
        "POST",
        "/items/download",
        {
            "outputRoot": str(output_root),
            "itemIds": [item_id],
            "outputPath": str(tmp_path / "download.zip"),
        },
    )
    assert download_status == 200
    assert Path(download_payload["archivePath"]).exists()

    save_status, save_payload = handle_request(
        "POST",
        "/settings/save",
        {
            "outputRoot": str(tmp_path / "next-runs"),
            "instanceName": "api-next",
            "apiPort": 19602,
        },
    )
    assert save_status == 200
    assert save_payload["outputRoot"] == str(tmp_path / "next-runs")
    assert save_payload["runtime"]["instanceName"] == "api-next"
    assert save_payload["runtime"]["apiPort"] == 19602


def _run_dirs(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.iterdir() if path.is_dir() and path.name.startswith("run-")),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )
