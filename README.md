# TimelineForPcInfo

`TimelineForPcInfo` is a local-first Windows host tool for capturing the current
state and hardware/software information of a Windows PC, writing a readable markdown report, and appending
Timeline-compatible item artifacts.

The product integration surface is the Python local API started by `start.ps1`.
The canonical product name is `TimelineForPcInfo`. Runtime integration uses
`productId: "pc"`, the Python package `timeline_for_pc_info`, environment
variables prefixed with `TIMELINE_FOR_PC_INFO_`, the
`TimelineForPcInfo-items-*.zip` archive prefix, the
`C:\apps\TimelineForPcInfo` directory, port `19600`, and the `to_text\pc`
output path.

## Host-Only Boundary

TimelineForPcInfo is intentionally host-only because the source data is the current
Windows machine state. Keep that host-side surface narrow:

- Allowed host-only work: Windows system inventory, current-user autostart, and
  local API process lifecycle.
- Keep Timeline integration behind the local HTTP API. Do not add product
  operation command runners.
- Do not add Docker settings just for consistency while the product has no
  Docker runtime.
- If later processing becomes heavy or no longer needs direct Windows access,
  move that processing behind a Docker worker and keep the Windows host API as a
  small capture/control adapter.

## What It Writes

Each capture writes one run directory with:

- `request.json`
- `snapshot.json`
- `snapshot_redacted.json`
- `report.md`
- `YYYYMMDDHHMM.md`
- `result.json`
- `manifest.json`
- `status.json`

Timeline item artifacts are written under the configured `outputRoot`:

- `items/<pc-id>/timeline.json`
- `items/<pc-id>/convert_info.json`
- `items.jsonl`
- `events.jsonl`
- `manifest.json`

Repeated captures append timeline events. If the material PC configuration did
not change, the event is still saved with `update_status: "unchanged"`.

See [OUTPUTS.md](OUTPUTS.md) for the concrete JSON structures, JSONL rows, and
download ZIP contents.

## Requirements

Required for normal live capture:

| Requirement | Purpose |
| --- | --- |
| Windows host | The product captures Windows PC state. |
| PowerShell | Runs the local collector script. |
| Python 3.11+ | Runs the capture pipeline behind the local API. |

Optional:

| Requirement | Purpose |
| --- | --- |
| NVIDIA utilities | Adds NVIDIA runtime details when available. |
| WSL | Adds WSL details when available. |
| `pytest` | Runs the development test suite. |

## API Usage

Run commands from `C:\apps\TimelineForPcInfo`.

Check local prerequisites:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:19600/doctor -Body '{}' -ContentType 'application/json'
```

Run a live capture:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:19600/capture -Body '{}' -ContentType 'application/json'
```

Run a deterministic mock capture:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:19600/capture -Body '{"mock":true,"mockProfile":"baseline","redactionProfile":"llm_safe"}' -ContentType 'application/json'
```

List Timeline items:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:19600/items/list -Body '{}' -ContentType 'application/json'
```

Create a Timeline-compatible ZIP:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:19600/items/download -Body '{"to":"C:\\apps\\Timeline\\data\\to_text\\pc\\downloads","overwrite":true}' -ContentType 'application/json'
```

## Settings

Persistent local settings live at the product root:

- `settings.example.json` is tracked.
- `settings.json` is local-only and ignored by Git.

Current supported shape:

```json
{
  "schemaVersion": 1,
  "runtime": {
    "instanceName": "7d3f91ab4e",
    "apiPort": 19600
  },
  "outputRoot": "C:/apps/Timeline/data/to_text/pc"
}
```

Supported settings:

- `runtime.instanceName`: local product instance name
- `outputRoot`: default output directory for captures and Timeline artifacts
- `runtime.apiPort`: port used by the local API

`mock_profile` and `redaction_profile` are command options, not persistent
settings.

Settings API calls:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:19600/settings/init -Body '{}' -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://localhost:19600/settings/status -Body '{}' -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://localhost:19600/settings/save -Body '{"outputRoot":"C:\\apps\\Timeline\\data\\to_text\\pc","instanceName":"7d3f91ab4e","apiPort":19600}' -ContentType 'application/json'
```

When settings are saved, unknown existing keys are preserved. This is important
for product-specific secrets or tokens in sibling products. TimelineForPcInfo does
not require a Hugging Face token.

## Local API

TimelineForPcInfo provides a small local API for Timeline integration.

```text
GET http://localhost:{runtime.apiPort}/health
```

The response body is a JSON boolean:

```json
true
```

Timeline-compatible API actions are also available:

```text
POST http://localhost:{runtime.apiPort}/capture
POST http://localhost:{runtime.apiPort}/doctor
POST http://localhost:{runtime.apiPort}/smoke-test
POST http://localhost:{runtime.apiPort}/settings/init
POST http://localhost:{runtime.apiPort}/settings/status
POST http://localhost:{runtime.apiPort}/settings/save
POST http://localhost:{runtime.apiPort}/items/list
POST http://localhost:{runtime.apiPort}/items/refresh
POST http://localhost:{runtime.apiPort}/items/download
```

`/capture` accepts optional capture settings using JSON field names such as
`outputRoot`, `mock`, `mockProfile`, and `redactionProfile`.

`/doctor` accepts `outputRoot`.

`/smoke-test` accepts `outputRoot`, `live`, and `redactionProfile`.

`/settings/save` accepts `outputRoot`, `instanceName`, and `apiPort`.

`/items/list` accepts `outputRoot`, `page`, and `pageSize`.

`/items/refresh` accepts the same optional capture settings using JSON field
names such as `outputRoot`, `mock`, `mockProfile`, and `redactionProfile`.

`/items/download` accepts `outputRoot`, `to` or `outputPath`, `overwrite`,
and `itemIds`.
Responses preserve the existing JSON payload shape so Timeline can use HTTP
calls without changing the data contract. The local API calls the Python capture
functions in-process; live Windows collection still uses the PowerShell
collector script as the OS data source.

Start or stop the local API process:

```powershell
.\start.ps1
.\stop.ps1
```

`start.ps1` uses `settings.json` by default. For local smoke checks, a temporary
port can be supplied:

```powershell
.\start.ps1 -Port 19601
```

## Always-On Mode

To keep the local API available after Windows logon, install the current-user
autostart entry:

```powershell
.\install-autostart.ps1
```

The installer first tries to register a current-user Scheduled Task. If the
current environment refuses Scheduled Task registration, it falls back to a
current-user Startup launcher that runs `watchdog.ps1`.

The always-on check calls `start.ps1` at logon and then repeats the same
idempotent start check every 5 minutes. If TimelineForPcInfo is already running,
`start.ps1` exits without starting a second process.

Remove the autostart entry:

```powershell
.\uninstall-autostart.ps1
```

Remove the task and stop the running local API:

```powershell
.\uninstall-autostart.ps1 -Stop
```

## Development

Run tests:

```powershell
python -m pytest
```

Check Python syntax:

```powershell
python -m compileall -q src tests
```
