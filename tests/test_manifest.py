from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_product_manifest_uses_api_runtime_launchers() -> None:
    manifest = json.loads((REPO_ROOT / "timeline-product.json").read_text(encoding="utf-8"))
    commands = manifest["commands"]
    removed_command_name = "cl" + "i"
    removed_script_name = removed_command_name + ".ps1"

    assert removed_command_name not in commands
    assert "primary" not in commands
    assert commands["start"]["path"] == "start.ps1"
    assert commands["stop"]["path"] == "stop.ps1"
    assert commands["installAutostart"]["path"] == "install-autostart.ps1"
    assert commands["uninstallAutostart"]["path"] == "uninstall-autostart.ps1"
    assert all(command["path"] != removed_script_name for command in commands.values())
    assert all(command["path"] != "timeline-for-pc-info.ps1" for command in commands.values())

    for command in commands.values():
        assert (REPO_ROOT / command["path"]).exists()


def test_product_manifest_declares_api_mode_with_health_probe() -> None:
    manifest = json.loads((REPO_ROOT / "timeline-product.json").read_text(encoding="utf-8"))
    settings_example = json.loads((REPO_ROOT / "settings.example.json").read_text(encoding="utf-8"))

    assert manifest["api"] == {
        "enabled": True,
        "connectionMode": "api",
        "healthPath": "/health",
        "defaultHost": "localhost",
        "defaultPort": 19600,
        "defaultBaseUrl": "http://localhost:19600",
    }
    assert manifest["runtime"]["hostApi"] is True
    assert manifest["runtime"]["healthApi"] is True
    assert manifest["runtime"]["usesDocker"] is False
    assert manifest["runtime"]["dockerManagedByTimeline"] is False
    assert manifest["runtime"]["hostOnlyResponsibilities"] == [
        "windowsSystemInventory",
        "currentUserAutostart",
        "hostApiLifecycle",
    ]
    assert manifest["runtime"]["dockerOffloadCandidates"] == [
        "snapshotNormalization",
        "reportRendering",
        "timelineArtifactPackaging",
    ]
    assert "instanceName" not in settings_example
    assert "apiHost" not in settings_example["runtime"]
    assert settings_example["runtime"]["instanceName"] == "7d3f91ab4e"
    assert settings_example["runtime"]["apiPort"] == manifest["api"]["defaultPort"]


def test_python_api_server_exposes_timeline_routes_without_legacy_pc_prefix() -> None:
    program = (REPO_ROOT / "src" / "timeline_for_pc_info" / "api_server.py").read_text(encoding="utf-8")

    assert 'route == "/health"' in program
    assert '"/pc/' not in program
    assert 'route == "/capture"' in program
    assert 'route == "/doctor"' in program
    assert 'route == "/smoke-test"' in program
    assert 'route == "/items/list"' in program
    assert 'route == "/items/refresh"' in program
    assert 'route == "/items/download"' in program
    assert 'route == "/settings/status"' in program
    assert "ProductOperationRunner" not in program
    assert "subprocess" not in program


def test_readme_documents_local_api() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    removed_script_name = "cl" + "i.ps1"

    assert f"powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\{removed_script_name}" not in readme
    assert "## Host-Only Boundary" in readme
    assert "Allowed host-only work: Windows system inventory" in readme
    assert "Do not add product" in readme
    assert "The product integration surface is the Python local API" in readme
    assert "TimelineForPcInfo provides a small local API for Timeline integration." in readme
    assert "GET http://localhost:{runtime.apiPort}/health" in readme
    assert "POST http://localhost:{runtime.apiPort}/items/download" in readme
    assert "## Always-On Mode" in readme
    assert ".\\install-autostart.ps1" in readme
    assert ".\\uninstall-autostart.ps1" in readme
    assert "rolled back" not in readme
    assert "/pc/" not in readme


def test_runtime_entrypoints_do_not_reference_legacy_cli_shim() -> None:
    removed_script_name = "cl" + "i.ps1"
    runtime_paths = [
        REPO_ROOT / "timeline-product.json",
        REPO_ROOT / "start.ps1",
        REPO_ROOT / "stop.ps1",
        REPO_ROOT / "watchdog.ps1",
        REPO_ROOT / "install-autostart.ps1",
        REPO_ROOT / "uninstall-autostart.ps1",
        REPO_ROOT / "settings.example.json",
    ]
    runtime_paths.extend((REPO_ROOT / "src" / "timeline_for_pc_info").glob("*.py"))

    for path in runtime_paths:
        assert removed_script_name not in path.read_text(encoding="utf-8")


def test_start_script_uses_python_api_server_instead_of_dotnet_runner() -> None:
    start_script = (REPO_ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "timeline_for_pc_info.api_server" in start_script
    assert "dotnet" not in start_script


def test_tracked_docs_and_examples_only_point_at_allowed_timeline_data_path() -> None:
    checked_paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "settings.example.json",
        REPO_ROOT / "timeline-product.json",
    ]

    for path in checked_paths:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"C:(?:\\|/)apps(?:\\|/)Timeline(?:\\|/)([^`\"'\s]+)", text):
            assert match.group(1).replace("\\", "/").startswith("data/to_text/pc")
        for match in re.finditer(r"/mnt/c/apps/Timeline/([^`\"'\s]+)", text):
            assert match.group(1).startswith("data/to_text/pc")
