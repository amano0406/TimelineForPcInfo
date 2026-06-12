# TimelineForPcInfo Output Contract

This document describes the files and JSON payloads written by TimelineForPcInfo.
Examples use the default Windows output root:

```text
C:\apps\Timeline\data\to_text\pc
```

Stage 1 of the rename changes the user-facing product name only. Compatibility
fields and paths such as `product: "TimelineForPcInfo"`,
`artifact_type: "timeline_for_pc_info_items_download"`, the
`TimelineForPcInfo-items-*.zip` prefix, and `C:\apps\TimelineForPcInfo` remain unchanged
until the contract migration stage.

## Conventions

- Timestamps are UTC ISO-8601 strings ending in `Z`.
- File payloads use `schema_version`.
- Some API JSON responses also include camelCase aliases such as `runDir`,
  `archivePath`, and `itemId` for application integration.
- `snapshot.json` can contain local machine details. Use
  `snapshot_redacted.json` or `report.md` for handoff to tools that should not
  see host-identifying values.

## Directory Layout

One capture creates one run directory and updates the Timeline item store:

```text
outputRoot/
  run-20260514-051138-1a2b3c4d/
    request.json
    status.json
    snapshot.json
    snapshot_redacted.json
    report.md
    202605140511.md
    manifest.json
    result.json
  items/
    pc-0123456789abcdef/
      timeline.json
      convert_info.json
  items.jsonl
  events.jsonl
  manifest.json
  downloads/
    TimelineForPcInfo-items-20260514-051200.zip
```

## Run Directory Files

### request.json

Records how the capture was requested.

```json
{
  "schema_version": 1,
  "run_id": "run-20260514-051138-1a2b3c4d",
  "created_at_utc": "2026-05-13T20:11:38Z",
  "capture_mode": "windows",
  "mock_profile": null,
  "redaction_profile": "llm_safe",
  "output_root": "C:\\apps\\Timeline\\data\\to_text\\pc"
}
```

`capture_mode` is `windows` for live collection and `mock` for deterministic
development captures.

### status.json

Tracks the latest run state. During collection, `state` is `running`. After
completion, the file is overwritten with the final status.

```json
{
  "schema_version": 1,
  "run_id": "run-20260514-051138-1a2b3c4d",
  "state": "completed",
  "current_stage": "completed",
  "message": "Capture completed.",
  "started_at_utc": "2026-05-13T20:11:38Z",
  "updated_at_utc": "2026-05-13T20:11:40Z",
  "completed_at_utc": "2026-05-13T20:11:40Z"
}
```

### snapshot.json

Raw normalized PC snapshot.

```json
{
  "schema_version": 1,
  "captured_at_utc": "2026-05-13T20:11:39Z",
  "capture_mode": "windows",
  "os": {
    "product_name": "Windows 11 Pro",
    "version": "10.0.26100",
    "build_number": "26100",
    "architecture": "64-bit"
  },
  "host": {
    "name": "DESKTOP-EXAMPLE",
    "manufacturer": "Example Manufacturer",
    "model": "Example Model",
    "system_type": "x64-based PC",
    "total_memory_bytes": 34359738368,
    "motherboard": {
      "manufacturer": "Example Board Vendor",
      "product": "Example Board"
    }
  },
  "processors": [
    {
      "name": "Example CPU",
      "cores": 8,
      "logical_processors": 16,
      "max_clock_mhz": 4800
    }
  ],
  "gpus": [
    {
      "name": "Example GPU",
      "driver_version": "32.0.0.0",
      "adapter_ram_bytes": 8589934592
    }
  ],
  "physical_disks": [
    {
      "name": "Example NVMe",
      "media_type": "SSD",
      "bus_type": "NVMe",
      "size_bytes": 1000204886016,
      "health_status": "Healthy"
    }
  ],
  "volumes": [
    {
      "name": "C:",
      "root": "C:\\",
      "used_bytes": 420000000000,
      "free_bytes": 580000000000,
      "total_bytes": 1000000000000
    }
  ],
  "applications": [
    {
      "name": "Docker Desktop",
      "version": "4.41.0",
      "publisher": "Docker Inc."
    }
  ],
  "details": {
    "platform": {
      "computer_name": "DESKTOP-EXAMPLE",
      "uuid": "00000000-0000-0000-0000-000000000000"
    },
    "bios": {},
    "os_details": {},
    "cpu_details": {},
    "memory_details": {},
    "storage_details": {},
    "network": {},
    "audio": {},
    "virtualization": {},
    "wsl": {}
  }
}
```

The `details` object can include richer nested data from PowerShell, NVIDIA
utilities, WSL, storage, network, audio, and virtualization probes when
available.

### snapshot_redacted.json

Same shape as `snapshot.json`, but selected host-identifying values are
redacted for handoff. With `llm_safe`, host names are replaced, application
publishers are removed, and network adapter `ipv4`, `ipv6`, and `dhcp_server`
values are replaced when present.

```json
{
  "schema_version": 1,
  "captured_at_utc": "2026-05-13T20:11:39Z",
  "capture_mode": "windows",
  "host": {
    "name": "[redacted-host]",
    "manufacturer": "Example Manufacturer",
    "model": "Example Model",
    "system_type": "x64-based PC",
    "total_memory_bytes": 34359738368,
    "motherboard": {
      "manufacturer": "Example Board Vendor",
      "product": "Example Board"
    }
  },
  "applications": [
    {
      "name": "Docker Desktop",
      "version": "4.41.0",
      "publisher": null
    }
  ],
  "details": {
    "platform": {
      "computer_name": "[redacted-host]",
      "uuid": "00000000-0000-0000-0000-000000000000"
    },
    "network": {
      "adapters": [
        {
          "name": "Ethernet",
          "kind": "wired",
          "ipv4": "[redacted]",
          "ipv6": "[redacted]",
          "dhcp_server": "[redacted]"
        }
      ]
    }
  }
}
```

### result.json

Final machine-readable result for a capture. The `POST /capture` and
`POST /items/refresh` API responses are based on this file.

```json
{
  "schema_version": 1,
  "run_id": "run-20260514-051138-1a2b3c4d",
  "state": "completed",
  "run_dir": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d",
  "snapshot_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d\\snapshot.json",
  "report_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d\\report.md",
  "snapshot_redacted_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d\\snapshot_redacted.json",
  "export_markdown_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d\\202605140511.md",
  "timeline_artifacts": {
    "item_id": "pc-0123456789abcdef",
    "update_status": "first_seen",
    "event_id": "evt-0123456789ab",
    "snapshot_fingerprint": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "previous_snapshot_fingerprint": null,
    "item_dir": "C:\\apps\\Timeline\\data\\to_text\\pc\\items\\pc-0123456789abcdef",
    "timeline_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\items\\pc-0123456789abcdef\\timeline.json",
    "convert_info_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\items\\pc-0123456789abcdef\\convert_info.json",
    "items_index_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\items.jsonl",
    "events_index_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\events.jsonl",
    "root_manifest_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\manifest.json"
  },
  "completed_at_utc": "2026-05-13T20:11:40Z"
}
```

`update_status` is:

- `first_seen`: first event for this PC item
- `unchanged`: no material PC configuration change from the previous capture
- `changed`: material PC configuration changed

### manifest.json

Run-local manifest listing files produced by this capture.

```json
{
  "schema_version": 1,
  "run_id": "run-20260514-051138-1a2b3c4d",
  "files": [
    "request.json",
    "status.json",
    "result.json",
    "manifest.json",
    "snapshot.json",
    "snapshot_redacted.json",
    "report.md",
    "202605140511.md"
  ],
  "redaction_profile": "llm_safe",
  "timeline_artifacts": {
    "item_id": "pc-0123456789abcdef",
    "update_status": "first_seen",
    "event_id": "evt-0123456789ab",
    "snapshot_fingerprint": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "previous_snapshot_fingerprint": null,
    "item_dir": "C:\\apps\\Timeline\\data\\to_text\\pc\\items\\pc-0123456789abcdef",
    "timeline_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\items\\pc-0123456789abcdef\\timeline.json",
    "convert_info_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\items\\pc-0123456789abcdef\\convert_info.json",
    "items_index_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\items.jsonl",
    "events_index_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\events.jsonl",
    "root_manifest_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\manifest.json"
  }
}
```

## Timeline Item Store

### outputRoot/manifest.json

Root manifest for Timeline-compatible item artifacts.

```json
{
  "schema_version": 1,
  "product": "TimelineForPcInfo",
  "updated_at_utc": "2026-05-13T20:11:40Z",
  "item_count": 1,
  "event_count": 3,
  "files": [
    "items.jsonl",
    "events.jsonl",
    "items/pc-0123456789abcdef/timeline.json",
    "items/pc-0123456789abcdef/convert_info.json"
  ]
}
```

### items/<pc-id>/timeline.json

Full event history for one Windows PC item.

```json
{
  "schema_version": 1,
  "item_id": "pc-0123456789abcdef",
  "item_type": "windows_pc",
  "title": "Windows PC snapshot history",
  "created_at_utc": "2026-05-13T20:11:38Z",
  "updated_at_utc": "2026-05-13T20:20:00Z",
  "latest_run_id": "run-20260514-052000-aabbccdd",
  "latest_event_id": "evt-abcdef012345",
  "latest_update_status": "changed",
  "latest_snapshot_fingerprint": "sha256:abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345",
  "events": [
    {
      "schema_version": 1,
      "event_id": "evt-abcdef012345",
      "event_type": "pc_snapshot_captured",
      "item_id": "pc-0123456789abcdef",
      "occurred_at_utc": "2026-05-13T20:19:59Z",
      "recorded_at_utc": "2026-05-13T20:20:00Z",
      "run_id": "run-20260514-052000-aabbccdd",
      "capture_mode": "windows",
      "update_status": "changed",
      "summary": "Material PC configuration change detected. OS build 26100; GPUs: 1; physical disks: 1; installed apps: 1.",
      "snapshot_fingerprint": "sha256:abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345",
      "previous_snapshot_fingerprint": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "artifact_refs": {
        "run_dir": "run-20260514-052000-aabbccdd",
        "report_md": "run-20260514-052000-aabbccdd/report.md",
        "export_md": "run-20260514-052000-aabbccdd/202605140519.md",
        "snapshot_redacted_json": "run-20260514-052000-aabbccdd/snapshot_redacted.json"
      }
    }
  ]
}
```

### items/<pc-id>/convert_info.json

Latest conversion and fingerprint metadata for the PC item.

```json
{
  "schema_version": 1,
  "product": "TimelineForPcInfo",
  "item_id": "pc-0123456789abcdef",
  "item_type": "windows_pc",
  "source_type": "local_windows_host",
  "created_at_utc": "2026-05-13T20:11:38Z",
  "updated_at_utc": "2026-05-13T20:20:00Z",
  "latest_run_id": "run-20260514-052000-aabbccdd",
  "latest_event_id": "evt-abcdef012345",
  "update_status": "changed",
  "capture_mode": "windows",
  "redaction_profile": "llm_safe",
  "snapshot_fingerprint": "sha256:abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345",
  "previous_snapshot_fingerprint": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "fingerprint_scope": "material_pc_configuration",
  "fingerprint_ignored_fields": [
    "captured_at_utc",
    "host.name",
    "details.platform.computer_name",
    "details.platform.uuid",
    "volumes.used_bytes",
    "volumes.free_bytes",
    "details.gpu_runtime",
    "details.os_details.last_boot_local",
    "details.wsl.running_distributions",
    "network adapter IP/runtime-only fields"
  ],
  "artifact_refs": {
    "run_dir": "run-20260514-052000-aabbccdd",
    "report_md": "run-20260514-052000-aabbccdd/report.md",
    "export_md": "run-20260514-052000-aabbccdd/202605140519.md",
    "snapshot_redacted_json": "run-20260514-052000-aabbccdd/snapshot_redacted.json"
  }
}
```

### items.jsonl

One JSON object per line for item indexing.

```jsonl
{"convert_info_path":"items/pc-0123456789abcdef/convert_info.json","item_id":"pc-0123456789abcdef","item_type":"windows_pc","latest_event_id":"evt-abcdef012345","latest_run_id":"run-20260514-052000-aabbccdd","latest_snapshot_fingerprint":"sha256:abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345","latest_update_status":"changed","schema_version":1,"timeline_path":"items/pc-0123456789abcdef/timeline.json","title":"Windows PC snapshot history","updated_at_utc":"2026-05-13T20:20:00Z"}
```

### events.jsonl

One JSON object per line for capture events. New captures append a row.

```jsonl
{"artifact_refs":{"export_md":"run-20260514-052000-aabbccdd/202605140519.md","report_md":"run-20260514-052000-aabbccdd/report.md","run_dir":"run-20260514-052000-aabbccdd","snapshot_redacted_json":"run-20260514-052000-aabbccdd/snapshot_redacted.json"},"capture_mode":"windows","event_id":"evt-abcdef012345","event_type":"pc_snapshot_captured","item_id":"pc-0123456789abcdef","occurred_at_utc":"2026-05-13T20:19:59Z","previous_snapshot_fingerprint":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","recorded_at_utc":"2026-05-13T20:20:00Z","run_id":"run-20260514-052000-aabbccdd","schema_version":1,"snapshot_fingerprint":"sha256:abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345abcdef012345","summary":"Material PC configuration change detected. OS build 26100; GPUs: 1; physical disks: 1; installed apps: 1.","update_status":"changed"}
```

## API JSON Responses

### POST /capture and POST /items/refresh

The response includes `result.json` plus API-level fields:

```json
{
  "schema_version": 1,
  "ok": true,
  "run_dir": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d",
  "runDir": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d",
  "run_id": "run-20260514-051138-1a2b3c4d",
  "state": "completed",
  "snapshot_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d\\snapshot.json",
  "report_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d\\report.md",
  "snapshot_redacted_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d\\snapshot_redacted.json",
  "export_markdown_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\run-20260514-051138-1a2b3c4d\\202605140511.md",
  "timeline_artifacts": {
    "item_id": "pc-0123456789abcdef",
    "update_status": "first_seen",
    "event_id": "evt-0123456789ab"
  },
  "completed_at_utc": "2026-05-13T20:11:40Z"
}
```

### POST /items/list

```json
{
  "schema_version": 1,
  "ok": true,
  "output_root": "C:\\apps\\Timeline\\data\\to_text\\pc",
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 1,
    "returned": 1,
    "has_next": false
  },
  "item_count": 1,
  "items": [
    {
      "schema_version": 1,
      "item_id": "pc-0123456789abcdef",
      "itemId": "pc-0123456789abcdef",
      "item_type": "windows_pc",
      "title": "Windows PC snapshot history",
      "created_at_utc": "2026-05-13T20:11:38Z",
      "updated_at_utc": "2026-05-13T20:20:00Z",
      "event_count": 3,
      "latest_update_status": "changed",
      "timeline_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\items\\pc-0123456789abcdef\\timeline.json",
      "convert_info_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\items\\pc-0123456789abcdef\\convert_info.json"
    }
  ]
}
```

### POST /items/download

```json
{
  "schema_version": 1,
  "ok": true,
  "archive_path": "C:\\apps\\Timeline\\data\\to_text\\pc\\downloads\\TimelineForPcInfo-items-20260514-052100.zip",
  "archivePath": "C:\\apps\\Timeline\\data\\to_text\\pc\\downloads\\TimelineForPcInfo-items-20260514-052100.zip",
  "item_count": 1,
  "event_count": 3
}
```

### POST /settings/status and POST /settings/save

```json
{
  "schemaVersion": 1,
  "ok": true,
  "settings_path": "C:\\apps\\TimelineForPcInfo\\settings.json",
  "outputRoot": "C:\\apps\\Timeline\\data\\to_text\\pc",
  "runtime": {
    "instanceName": "7d3f91ab4e",
    "api_port": 19600,
    "apiPort": 19600
  }
}
```

### POST /doctor

```json
{
  "schema_version": 1,
  "ok": true,
  "output_root": "C:\\apps\\Timeline\\data\\to_text\\pc",
  "integration": {
    "state": "recordable",
    "item_type": "windows_pc"
  },
  "checks": [
    {
      "name": "PowerShell",
      "requirement": "required",
      "status": "OK",
      "message": "PowerShell is available."
    }
  ]
}
```

### Error JSON

API actions return this shape for handled errors:

```json
{
  "schema_version": 1,
  "ok": false,
  "error": {
    "message": "Archive already exists: C:\\apps\\Timeline\\data\\to_text\\pc\\downloads\\TimelineForPcInfo-items-20260514-052100.zip"
  }
}
```

## Download ZIP

`POST /items/download` creates a ZIP for Timeline ingestion. Its structure is:

```text
manifest.json
README.md
items.jsonl
events.jsonl
items/pc-0123456789abcdef/timeline.json
items/pc-0123456789abcdef/convert_info.json
```

ZIP `manifest.json`:

```json
{
  "schema_version": 1,
  "artifact_type": "timeline_for_pc_info_items_download",
  "product": "TimelineForPcInfo",
  "created_at_utc": "2026-05-13T20:21:00Z",
  "item_count": 1,
  "event_count": 3,
  "files": {
    "items": "items.jsonl",
    "events": "events.jsonl"
  }
}
```

## Non-JSON Outputs

- `report.md`: human-readable Markdown report for the current capture.
- `YYYYMMDDHHMM.md`: exported copy of `report.md` for handoff and ingestion.
- ZIP `README.md`: short description of the ZIP contents.
