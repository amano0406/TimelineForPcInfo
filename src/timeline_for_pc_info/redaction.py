from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
from typing import Any

from timeline_for_pc_info.models import ApplicationInfo
from timeline_for_pc_info.models import HostInfo
from timeline_for_pc_info.models import Snapshot


REDACTION_PROFILES = ("none", "llm_safe")


def redact_snapshot(snapshot: Snapshot, profile: str) -> Snapshot:
    if profile == "none":
        return snapshot
    if profile != "llm_safe":
        raise ValueError(f"Unknown redaction profile: {profile}")

    return replace(
        snapshot,
        host=_redact_host(snapshot.host),
        applications=tuple(_redact_application(app) for app in snapshot.applications),
        details=_redact_details(snapshot.details),
    )


def _redact_host(host: HostInfo) -> HostInfo:
    if host.name:
        return replace(host, name="[redacted-host]")
    return host


def _redact_application(app: ApplicationInfo) -> ApplicationInfo:
    return replace(app, publisher=None)


def _redact_details(details: dict[str, Any]) -> dict[str, Any]:
    redacted = deepcopy(details)

    platform = redacted.get("platform")
    if isinstance(platform, dict) and platform.get("computer_name"):
        platform["computer_name"] = "[redacted-host]"

    network = redacted.get("network")
    if isinstance(network, dict):
        adapters = network.get("adapters")
        if isinstance(adapters, list):
            for item in adapters:
                if not isinstance(item, dict):
                    continue
                for key in ("ipv4", "ipv6", "dhcp_server"):
                    if item.get(key):
                        item[key] = "[redacted]"

    return redacted
