from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from http import HTTPStatus
from http.client import HTTPConnection
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(os.name != "nt", reason="start.ps1 and stop.ps1 are Windows launchers.")


def test_start_stop_scripts_run_health_api_without_legacy_launcher(tmp_path: Path) -> None:
    product_root = tmp_path / "product"
    output_root = tmp_path / "runs"
    output_root.mkdir(parents=True)
    _copy_script_runtime(product_root)

    settings = {
        "schemaVersion": 1,
        "outputRoot": str(output_root),
        "runtime": {
            "instanceName": "7d3f91ab4e",
            "apiPort": 19600,
        },
    }
    (product_root / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    removed_script_name = "cl" + "i.ps1"
    assert not (product_root / removed_script_name).exists()

    port = _free_port()
    _run_powershell(product_root, "start.ps1", "-Port", str(port))
    try:
        assert _wait_for_health(f"localhost:{port}") is True
        assert (product_root / ".runtime" / "health.pid").exists()
    finally:
        _run_powershell(product_root, "stop.ps1")

    assert not (product_root / ".runtime" / "health.pid").exists()


def test_start_script_rejects_invalid_port(tmp_path: Path) -> None:
    product_root = tmp_path / "product"
    _copy_script_runtime(product_root)

    result = _run_powershell_raw(product_root, "start.ps1", "-Port", "70000")

    assert result.returncode != 0
    assert "between 1 and 65535" in result.stdout + result.stderr
    assert not (product_root / ".runtime" / "health.pid").exists()


def test_autostart_scripts_register_current_user_scheduled_task() -> None:
    removed_script_name = "cl" + "i.ps1"
    install_script = (REPO_ROOT / "install-autostart.ps1").read_text(encoding="utf-8")
    uninstall_script = (REPO_ROOT / "uninstall-autostart.ps1").read_text(encoding="utf-8")
    watchdog_script = (REPO_ROOT / "watchdog.ps1").read_text(encoding="utf-8")

    assert "Register-ScheduledTask" in install_script
    assert "New-ScheduledTaskTrigger -AtLogOn" in install_script
    assert "RepetitionInterval" in install_script
    assert "New-ScheduledTaskPrincipal" not in install_script
    assert "LeastPrivilege" not in install_script
    assert "Startup" in install_script
    assert "watchdog.ps1" in install_script
    assert "start.ps1" in install_script
    assert removed_script_name not in install_script

    assert "Unregister-ScheduledTask" in uninstall_script
    assert "watchdog.pid" in uninstall_script
    assert "stop.ps1" in uninstall_script
    assert removed_script_name not in uninstall_script

    assert "Start-Sleep -Seconds $IntervalSeconds" in watchdog_script
    assert "start.ps1" in watchdog_script
    assert removed_script_name not in watchdog_script


def _copy_script_runtime(product_root: Path) -> None:
    product_root.mkdir(parents=True)
    for name in (
        "start.ps1",
        "stop.ps1",
        "install-autostart.ps1",
        "uninstall-autostart.ps1",
        "settings.example.json",
    ):
        shutil.copy2(REPO_ROOT / name, product_root / name)
    shutil.copytree(
        REPO_ROOT / "src",
        product_root / "src",
        ignore=shutil.ignore_patterns("bin", "obj", "__pycache__"),
    )


def _run_powershell(product_root: Path, script_name: str, *args: str) -> None:
    result = _run_powershell_raw(product_root, script_name, *args)
    assert result.returncode == 0, result.stdout + result.stderr


def _run_powershell_raw(product_root: Path, script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(product_root / script_name),
            *args,
        ],
        cwd=product_root,
        text=True,
        capture_output=True,
        timeout=120,
    )


def _wait_for_health(base_url: str) -> bool:
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            status, text = _request_text(base_url, "GET", "/health")
            if status == HTTPStatus.OK:
                return json.loads(text)
        except OSError:
            pass
        time.sleep(0.5)
    raise TimeoutError("TimelineForPC health API did not answer /health in time.")


def _request_text(base_url: str, method: str, path: str) -> tuple[int, str]:
    connection = HTTPConnection(base_url, timeout=30)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        connection.close()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
