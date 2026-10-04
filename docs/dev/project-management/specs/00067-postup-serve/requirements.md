# postup E: serve (FastAPI + SSE + confinement)

<!-- requirements; migrated from PRD 00067 flat file -->

## Overview

### Problem Statement
The rebuilt web UI (00065/00066) has no delivery path — the single-file HTML export was dropped by discovery decision Q11, making `postup serve` the only web delivery. This PRD lands the FastAPI serving layer per the bim-serve pattern: REST payload endpoints, SSE refresh, collect/enrich triggers from the UI, and the 00042 localhost confinement posture.

### Target Users
Solo developer running `postup serve` and working in the browser UI; PRD 00070's cutover parity check, which compares this server's brief data against the retiring skill's.

### Success Metrics
- `postup serve` on a core+`postup-web` install serves the committed frontend and live payload data on localhost.
- Editing/re-running collect updates the open browser via SSE without manual reload.
- Collect and enrich are triggerable from the UI and report success/failure in the UI.
- Confinement holds: non-localhost requests rejected, request-derived paths confined, auth per bim conventions; gems gates green.

## Functional Decomposition

### Capability: Serve application
The FastAPI app and its safety posture.

#### Feature: App factory and serve command
- **Description**: `postup serve` builds the FastAPI app (bim-serve app-factory pattern) and runs uvicorn.
- **Inputs**: `PostupSettings` (out_dir, host/port defaults), committed frontend build.
- **Outputs**: `CommandResult` on startup failure; a running localhost server otherwise.
- **Behavior**: fastapi/uvicorn/watchfiles are optional deps behind a new `postup-web` extra (bim/bim-web precedent); missing extra yields `console.require_import()` guidance, not a traceback. Whether serve auto-runs a collect on start or serves the last data until refreshed is an open decision for design (see Risks).

#### Feature: Confinement (00042 posture)
- **Description**: The bim-serve security posture applied from day one.
- **Inputs**: HTTP requests.
- **Outputs**: Denied out-of-scope requests.
- **Behavior**: Bind localhost only; `TrustedHostMiddleware`; auth per bim conventions; every request-derived filesystem path `resolve()`d and asserted under `out_dir` (or the frontend build dir) before any read — the AGENTS.md confine-request-paths invariant.

### Capability: Live data plane
Payload access, refresh, and actions from the UI.

#### Feature: REST payload endpoints
- **Description**: Endpoints the frontend loader (00065) fetches: current payload (`data.json` + `epics.json` if present), previous payload, history.
- **Inputs**: File contracts under `out_dir`.
- **Outputs**: JSON responses mirroring the file contracts (schema_version passed through).
- **Behavior**: Route surface follows the design doc — bim's action-registry pattern is the default candidate (AGENTS.md exemplar); endpoints return the not-yet-collected state explicitly (empty portfolio hint) rather than 500.

#### Feature: SSE refresh
- **Description**: Push a refresh event to open browsers when output files change.
- **Inputs**: `out_dir` file changes (watchfiles, bim `_sse.py` pattern).
- **Outputs**: SSE event stream endpoint.
- **Behavior**: Frontend re-fetches payload on event; watcher tolerates the atomic-replace write pattern (00063) without duplicate storms (debounce).

#### Feature: Collect/enrich triggers
- **Description**: Run collect or enrich from the UI.
- **Inputs**: Trigger requests from the frontend.
- **Outputs**: Action status (started/succeeded/failed with the `CommandResult` message).
- **Behavior**: Triggers invoke the same command classes as the CLI through the composition root (all-interface rule — one action, one implementation; no reimplementation in routes). Concurrent trigger requests while a run is active are rejected with an "already running" status.
