from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from timeline_for_pc.doctor import doctor_result_payload
from timeline_for_pc.doctor import run_doctor
from timeline_for_pc.items import download_items
from timeline_for_pc.items import download_result_payload
from timeline_for_pc.items import list_items
from timeline_for_pc.redaction import REDACTION_PROFILES
from timeline_for_pc.runner import run_capture
from timeline_for_pc.settings import SettingsError
from timeline_for_pc.settings import init_settings
from timeline_for_pc.settings import load_settings
from timeline_for_pc.settings import save_settings
from timeline_for_pc.settings import settings_path
from timeline_for_pc.smoke import run_smoke_test


MOCK_PROFILES = ("baseline", "upgraded")


def handle_request(method: str, path: str, request: dict[str, Any] | None) -> tuple[int, Any]:
    route = path.rstrip("/") or "/"
    if method == "GET" and route == "/health":
        return HTTPStatus.OK, health_payload()
    if method != "POST":
        return HTTPStatus.NOT_FOUND, error_payload(f"Endpoint not found: {method} {path}")

    try:
        payload = request or {}
        if route == "/capture":
            return HTTPStatus.OK, capture_payload(payload)
        if route == "/doctor":
            status, result = doctor_payload(payload)
            return status, result
        if route == "/smoke-test":
            status, result = smoke_test_payload(payload)
            return status, result
        if route == "/settings/init":
            return HTTPStatus.OK, settings_init_payload()
        if route == "/settings/status":
            return HTTPStatus.OK, settings_status_payload()
        if route == "/settings/save":
            return HTTPStatus.OK, settings_save_payload(payload)
        if route == "/items/list":
            return HTTPStatus.OK, items_list_payload(payload)
        if route == "/items/refresh":
            return HTTPStatus.OK, capture_payload(payload)
        if route == "/items/download":
            return HTTPStatus.OK, items_download_payload(payload)
    except (OSError, ValueError, SettingsError) as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, error_payload(str(exc), exc.__class__.__name__)
    except Exception as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, error_payload(str(exc), exc.__class__.__name__)

    return HTTPStatus.NOT_FOUND, error_payload(f"Endpoint not found: {method} {path}")


def health_payload() -> bool:
    try:
        _ = load_settings()
        return (Path(product_root()) / "src" / "timeline_for_pc").is_dir()
    except Exception:
        return False


def capture_payload(request: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    redaction_profile = require_choice(
        "redaction_profile",
        get_string_any(request, ["redactionProfile", "redaction_profile"]) or settings.redaction_profile,
        REDACTION_PROFILES,
    )
    mock_profile = require_choice(
        "mock_profile",
        get_string_any(request, ["mockProfile", "mock_profile"]) or settings.mock_profile,
        MOCK_PROFILES,
    )
    output_root = path_from_request(request, ["outputRoot", "output_root"], settings.output_root)
    run_dir = run_capture(
        output_root=output_root,
        mock=get_bool_any(request, ["mock"], False),
        mock_profile=mock_profile,
        redaction_profile=redaction_profile,
    )
    return capture_result_payload(run_dir)


def doctor_payload(request: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    settings = load_settings()
    output_root = path_from_request(request, ["outputRoot", "output_root"], settings.output_root)
    result = run_doctor(output_root=output_root)
    payload = doctor_result_payload(result, output_root=output_root)
    return (HTTPStatus.OK if result.ok else HTTPStatus.INTERNAL_SERVER_ERROR), payload


def smoke_test_payload(request: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    settings = load_settings()
    redaction_profile = require_choice(
        "redaction_profile",
        get_string_any(request, ["redactionProfile", "redaction_profile"]) or settings.redaction_profile,
        REDACTION_PROFILES,
    )
    output_root = path_from_request(request, ["outputRoot", "output_root"], settings.output_root / "_smoke")
    result = run_smoke_test(
        output_root=output_root,
        live=get_bool_any(request, ["live"], False),
        redaction_profile=redaction_profile,
    )
    payload = {
        "schemaVersion": 1,
        "ok": result.ok,
        "run_dir": str(result.run_dir),
        "runDir": str(result.run_dir),
        "export_path": str(result.export_path) if result.export_path is not None else "",
        "exportPath": str(result.export_path) if result.export_path is not None else "",
        "issues": result.issues,
    }
    return (HTTPStatus.OK if result.ok else HTTPStatus.INTERNAL_SERVER_ERROR), payload


def settings_init_payload() -> dict[str, Any]:
    result = init_settings()
    return {
        "schemaVersion": 1,
        "ok": True,
        "settings_path": str(result.path),
        "created": result.created,
    }


def settings_status_payload() -> dict[str, Any]:
    settings = load_settings()
    return settings_payload(path=settings_path(), settings=settings)


def settings_save_payload(request: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    result = save_settings(
        output_root=path_from_request(request, ["outputRoot", "output_root", "outputRootPath", "output_root_path"], current.output_root),
        instance_name=get_string_any(request, ["instanceName", "instance_name"]) or current.instance_name,
        api_port=get_optional_int_any(request, ["apiPort", "api_port"]) or current.api_port,
    )
    return settings_payload(path=result.path, settings=result.settings)


def items_list_payload(request: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    return list_items(
        output_root=path_from_request(request, ["outputRoot", "output_root"], settings.output_root),
        page=get_optional_int_any(request, ["page"]) or 1,
        page_size=get_optional_int_any(request, ["pageSize", "page_size"]) or 50,
    )


def items_download_payload(request: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    output_path = get_string_any(request, ["outputPath", "output_path", "output"])
    destination = get_string_any(request, ["to", "destinationPath", "destination_path", "downloadPath", "download_path"])
    result = download_items(
        output_root=path_from_request(request, ["outputRoot", "output_root"], settings.output_root),
        output_path=Path(output_path) if output_path else None,
        to_dir=Path(destination) if destination else None,
        overwrite=get_bool_any(request, ["overwrite"], False),
        item_ids=get_string_array_any(request, ["itemIds", "item_ids", "itemId", "item_id"]),
    )
    return download_result_payload(result)


def product_root() -> Path:
    configured = os.environ.get("TIMELINE_FOR_PC_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2]


def capture_result_payload(run_dir: Path) -> dict[str, Any]:
    result = read_json_object(run_dir / "result.json")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "ok": True,
        "run_dir": str(run_dir),
        "runDir": str(run_dir),
    }
    if result:
        payload.update(result)
    payload["ok"] = True
    payload["run_dir"] = str(run_dir)
    payload["runDir"] = str(run_dir)
    return payload


def settings_payload(*, path: Path, settings: Any) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "ok": True,
        "settings_path": str(path),
        "outputRoot": str(settings.output_root),
        "runtime": {
            "instanceName": settings.instance_name,
            "api_port": settings.api_port,
            "apiPort": settings.api_port,
        },
    }


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def require_choice(name: str, value: str, choices: tuple[str, ...]) -> str:
    if value not in choices:
        raise ValueError(f"{name} must be one of {', '.join(choices)}; got {value!r}.")
    return value


def path_from_request(request: dict[str, Any], names: list[str], fallback: Path) -> Path:
    value = get_string_any(request, names)
    return Path(value) if value else fallback


def get_optional_int_any(request: dict[str, Any], names: list[str]) -> int | None:
    for name in names:
        value = get_node(request, name)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                continue
    return None


def get_bool_any(request: dict[str, Any], names: list[str], fallback: bool) -> bool:
    for name in names:
        value = get_node(request, name)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
    return fallback


def get_string_any(request: dict[str, Any], names: list[str]) -> str:
    for name in names:
        value = get_node(request, name)
        if value is not None:
            text = convert_json_text(value)
            if text:
                return text
    return ""


def get_string_array_any(request: dict[str, Any], names: list[str]) -> list[str]:
    for name in names:
        value = get_node(request, name)
        if value is None:
            continue
        if isinstance(value, list):
            rows = [convert_json_text(item) for item in value if convert_json_text(item)]
        else:
            text = convert_json_text(value)
            rows = [part.strip() for part in text.replace("\r", ",").replace("\n", ",").split(",") if part.strip()]
        if rows:
            return rows
    return []


def get_node(request: dict[str, Any], name: str) -> Any:
    if name in request:
        return request[name]
    lowered = name.lower()
    for key, value in request.items():
        if key.lower() == lowered:
            return value
    return None


def convert_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(value, ensure_ascii=False).strip()


def error_payload(message: str, error_type: str = "Error") -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "ok": False,
        "error": {
            "type": error_type,
            "message": message,
        },
    }


class TimelineForPcApiHandler(BaseHTTPRequestHandler):
    server_version = "TimelineForPcApi/1.0"

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle(self) -> None:
        try:
            request = self._read_json()
            status_code, payload = handle_request(self.command, self.path.split("?", 1)[0], request)
        except Exception as exc:
            status_code, payload = HTTPStatus.INTERNAL_SERVER_ERROR, error_payload(str(exc), exc.__class__.__name__)
        self._write_json(status_code, payload)

    def _read_json(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        if not raw.strip():
            return None
        loaded = json.loads(raw.decode("utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("JSON request body must be an object.")
        return loaded

    def _write_json(self, status_code: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status_code))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    host = os.environ.get("TIMELINE_FOR_PC_API_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("TIMELINE_FOR_PC_API_PORT", "19600"))
    product_root_value = os.environ.get("TIMELINE_FOR_PC_ROOT", "")
    if product_root_value:
        os.environ["TIMELINE_FOR_PC_ROOT"] = str(Path(product_root_value).resolve())
    server = ThreadingHTTPServer((host, port), TimelineForPcApiHandler)
    print(f"TimelineForPC API listening on http://{host}:{port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
