from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from timeline_for_pc_info.runner import default_output_root


SETTINGS_EXAMPLE_FILENAME = "settings.example.json"
SETTINGS_FILENAME = "settings.json"
DEFAULT_API_PORT = 19600
DEFAULT_INSTANCE_NAME = "7d3f91ab4e"
DEFAULT_REDACTION_PROFILE = "llm_safe"
DEFAULT_MOCK_PROFILE = "baseline"


class SettingsError(RuntimeError):
    """Raised when local settings cannot be read or validated."""


@dataclass(frozen=True)
class AppSettings:
    output_root: Path
    instance_name: str = DEFAULT_INSTANCE_NAME
    redaction_profile: str = DEFAULT_REDACTION_PROFILE
    mock_profile: str = DEFAULT_MOCK_PROFILE
    api_port: int = DEFAULT_API_PORT


@dataclass(frozen=True)
class SettingsInitResult:
    path: Path
    created: bool


@dataclass(frozen=True)
class SettingsSaveResult:
    path: Path
    settings: AppSettings


def product_root() -> Path:
    configured = os.environ.get("TIMELINE_FOR_PC_INFO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2]


def settings_example_path(*, root: Path | None = None) -> Path:
    return (root or product_root()) / SETTINGS_EXAMPLE_FILENAME


def settings_path(*, root: Path | None = None) -> Path:
    return (root or product_root()) / SETTINGS_FILENAME


def default_settings() -> AppSettings:
    return AppSettings(
        output_root=default_output_root(),
        instance_name=DEFAULT_INSTANCE_NAME,
        redaction_profile=DEFAULT_REDACTION_PROFILE,
        mock_profile=DEFAULT_MOCK_PROFILE,
        api_port=DEFAULT_API_PORT,
    )


def load_settings(*, root: Path | None = None) -> AppSettings:
    path = settings_path(root=root)
    if not path.exists():
        return default_settings()

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SettingsError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SettingsError(f"Settings file must contain a JSON object: {path}")

    defaults = default_settings()
    runtime = raw.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
    return AppSettings(
        output_root=_path_from_setting(_first_setting(raw, {}, ("outputRoot", "output_root")), defaults.output_root),
        instance_name=_string_from_setting(
            _first_setting(runtime, raw, ("instance_name", "instanceName")),
            defaults.instance_name,
        ),
        redaction_profile=defaults.redaction_profile,
        mock_profile=defaults.mock_profile,
        api_port=_port_from_setting(
            _first_setting(runtime, raw, ("api_port", "apiPort")),
            defaults.api_port,
        ),
    )


def init_settings(*, root: Path | None = None) -> SettingsInitResult:
    target = settings_path(root=root)
    if target.exists():
        return SettingsInitResult(path=target, created=False)

    source = settings_example_path(root=root)
    if source.exists():
        content = source.read_text(encoding="utf-8")
    else:
        content = _default_settings_json()

    target.write_text(content, encoding="utf-8")
    return SettingsInitResult(path=target, created=True)


def save_settings(
    *,
    output_root: Path,
    instance_name: str | None = None,
    api_port: int | None = None,
    root: Path | None = None,
) -> SettingsSaveResult:
    target = settings_path(root=root)
    target.parent.mkdir(parents=True, exist_ok=True)
    defaults = default_settings()
    payload = _existing_settings_payload(target)
    runtime = payload.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
    settings = AppSettings(
        output_root=output_root,
        instance_name=_string_from_setting(
            instance_name,
            _string_from_setting(
                _first_setting(runtime, payload, ("instance_name", "instanceName")),
                defaults.instance_name,
            ),
        ),
        redaction_profile=defaults.redaction_profile,
        mock_profile=defaults.mock_profile,
        api_port=_port_from_setting(
            api_port,
            _port_from_setting(
                _first_setting(runtime, payload, ("api_port", "apiPort")),
                defaults.api_port,
            ),
        ),
    )
    runtime.pop("apiHost", None)
    runtime.pop("api_host", None)
    next_payload = _settings_payload_for_write(
        existing=payload,
        runtime=runtime,
        settings=settings,
    )
    target.write_text(json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return SettingsSaveResult(path=target, settings=settings)


def _default_settings_json() -> str:
    settings = default_settings()
    payload = _settings_payload_for_write(existing={}, runtime={}, settings=settings)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _settings_payload_for_write(
    *,
    existing: dict[str, Any],
    runtime: dict[str, Any],
    settings: AppSettings,
) -> dict[str, Any]:
    next_runtime: dict[str, Any] = {
        "instanceName": settings.instance_name,
        "apiPort": settings.api_port,
    }
    for key, value in runtime.items():
        if key in {"instanceName", "instance_name", "apiPort", "api_port", "apiHost", "api_host"}:
            continue
        next_runtime[key] = value

    next_payload: dict[str, Any] = {
        "schemaVersion": 1,
        "runtime": next_runtime,
        "outputRoot": str(settings.output_root),
    }
    for key, value in existing.items():
        if key in {
            "schemaVersion",
            "schema_version",
            "runtime",
            "output_root",
            "outputRoot",
            "instanceName",
            "instance_name",
            "apiHost",
            "api_host",
        }:
            continue
        next_payload[key] = value
    return next_payload


def _existing_settings_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SettingsError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SettingsError(f"Settings file must contain a JSON object: {path}")
    return dict(raw)


def _path_from_setting(value: Any, default: Path) -> Path:
    if value in (None, ""):
        return default
    return _normalize_path(str(value).strip())


def _normalize_path(value: str) -> Path:
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", value)
    if os.name != "nt" and match:
        drive = match.group(1).lower()
        rest = match.group(2).replace("\\", "/")
        return Path("/mnt") / drive / rest
    return Path(value)


def _string_from_setting(value: Any, default: str) -> str:
    if value in (None, ""):
        return default
    return str(value).strip()


def _port_from_setting(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"API port must be an integer: {value!r}") from exc
    if port < 1 or port > 65535:
        raise SettingsError(f"API port must be between 1 and 65535: {port}")
    return port


def _first_setting(primary: dict[str, Any], runtime: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in runtime:
            return runtime[name]
    for name in names:
        if name in primary:
            return primary[name]
    return None
