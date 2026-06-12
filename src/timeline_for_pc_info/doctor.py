from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


CheckStatus = Literal["OK", "WARN", "NG"]
CheckRequirement = Literal["required", "optional"]
ToolResolver = Callable[[str], str | None]
CommandChecker = Callable[[list[str]], bool]


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    requirement: CheckRequirement
    status: CheckStatus
    message: str


@dataclass(frozen=True)
class DoctorResult:
    ok: bool
    checks: tuple[DoctorCheck, ...]


def run_doctor(
    *,
    output_root: Path,
    tool_resolver: ToolResolver = shutil.which,
    command_checker: CommandChecker | None = None,
    python_version: tuple[int, int, int] | None = None,
) -> DoctorResult:
    command_checker = command_checker or _command_succeeds
    version = python_version or sys.version_info[:3]
    checks = [
        _check_python(version),
        _check_powershell(tool_resolver),
        _check_collector_script(),
        _check_output_root(output_root),
        _check_cmd(tool_resolver),
        _check_nvidia_smi(tool_resolver, command_checker),
        _check_wsl(tool_resolver, command_checker),
    ]
    return DoctorResult(
        ok=all(check.status != "NG" for check in checks),
        checks=tuple(checks),
    )


def format_doctor_result(result: DoctorResult) -> list[str]:
    lines = ["OK" if result.ok else "NG"]
    for check in result.checks:
        lines.append(f"- [{check.status}][{check.requirement}] {check.name}: {check.message}")
    return lines


def doctor_result_payload(result: DoctorResult, *, output_root: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "ok": result.ok,
        "output_root": str(output_root),
        "runtime": {
            "kind": "windows_host",
            "display_name": "Host execution",
            "state": "recordable" if result.ok else "not_ready",
            "message": "Runs directly on the Windows host. Docker is not required.",
        },
        "checks": [
            {
                "name": check.name,
                "requirement": check.requirement,
                "status": check.status,
                "message": check.message,
            }
            for check in result.checks
        ],
    }


def _check_python(version: tuple[int, int, int]) -> DoctorCheck:
    label = ".".join(str(part) for part in version[:3])
    if version >= (3, 11, 0):
        return DoctorCheck("Python", "required", "OK", f"{label} is supported.")
    return DoctorCheck("Python", "required", "NG", f"{label} is too old. Python 3.11 or newer is required.")


def _check_powershell(tool_resolver: ToolResolver) -> DoctorCheck:
    resolved = _which_first(("powershell.exe", "pwsh", "powershell"), tool_resolver)
    if resolved:
        return DoctorCheck("PowerShell", "required", "OK", f"Found at {resolved}.")
    return DoctorCheck("PowerShell", "required", "NG", "Not found. Live Windows collection cannot run without it.")


def _check_collector_script() -> DoctorCheck:
    script_path = Path(__file__).with_name("powershell") / "collect_snapshot.ps1"
    if script_path.exists():
        return DoctorCheck("Collector script", "required", "OK", f"Found at {script_path}.")
    return DoctorCheck("Collector script", "required", "NG", f"Missing expected script: {script_path}")


def _check_output_root(output_root: Path) -> DoctorCheck:
    if output_root.exists() and not output_root.is_dir():
        return DoctorCheck("Output root", "required", "NG", f"Exists but is not a directory: {output_root}")

    writable_target = output_root if output_root.exists() else _nearest_existing_parent(output_root)
    if not writable_target.exists():
        return DoctorCheck("Output root", "required", "NG", f"Parent directory does not exist: {writable_target}")
    if not writable_target.is_dir():
        return DoctorCheck("Output root", "required", "NG", f"Parent path is not a directory: {writable_target}")
    if not os.access(writable_target, os.W_OK):
        return DoctorCheck("Output root", "required", "NG", f"Directory is not writable: {writable_target}")
    return DoctorCheck("Output root", "required", "OK", f"Writable target is available: {writable_target}")


def _nearest_existing_parent(path: Path) -> Path:
    for parent in path.parents:
        if parent.exists():
            return parent
    return path.parent


def _check_cmd(tool_resolver: ToolResolver) -> DoctorCheck:
    resolved = _which_first(("cmd.exe", "cmd"), tool_resolver)
    if resolved:
        return DoctorCheck("cmd.exe", "optional", "OK", f"Found at {resolved}.")
    return DoctorCheck("cmd.exe", "optional", "WARN", "Not found. NVIDIA runtime and WSL detail checks may be skipped.")


def _check_nvidia_smi(tool_resolver: ToolResolver, command_checker: CommandChecker) -> DoctorCheck:
    resolved = _which_first(("nvidia-smi", "nvidia-smi.exe"), tool_resolver)
    if resolved:
        return DoctorCheck("nvidia-smi", "optional", "OK", f"Found at {resolved}.")

    cmd = _which_first(("cmd.exe", "cmd"), tool_resolver)
    if cmd and command_checker([cmd, "/c", "where", "nvidia-smi"]):
        return DoctorCheck("nvidia-smi", "optional", "OK", "Available from Windows command prompt.")

    return DoctorCheck(
        "nvidia-smi",
        "optional",
        "WARN",
        "Not found. Basic GPU info can still be collected, but NVIDIA runtime stats will be skipped.",
    )


def _check_wsl(tool_resolver: ToolResolver, command_checker: CommandChecker) -> DoctorCheck:
    resolved = _which_first(("wsl.exe", "wsl"), tool_resolver)
    if resolved:
        return DoctorCheck("wsl.exe", "optional", "OK", f"Found at {resolved}.")

    cmd = _which_first(("cmd.exe", "cmd"), tool_resolver)
    if cmd and command_checker([cmd, "/c", "where", "wsl.exe"]):
        return DoctorCheck("wsl.exe", "optional", "OK", "Available from Windows command prompt.")

    return DoctorCheck("wsl.exe", "optional", "WARN", "Not found. WSL details will be skipped.")


def _which_first(names: tuple[str, ...], tool_resolver: ToolResolver) -> str | None:
    for name in names:
        resolved = tool_resolver(name)
        if resolved:
            return resolved
    return None


def _command_succeeds(args: list[str]) -> bool:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
