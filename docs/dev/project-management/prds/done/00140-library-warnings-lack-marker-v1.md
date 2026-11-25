---
design: required
default_model: sonnet
model_tier_rationale: small logging-to-console bridge, but it must keep the library interface-agnostic
---

# Config library warnings print as bare log lines without the ⚠ marker

Source: agoge runs `docs/dev/project-management/audit-results/agoge-2026-11-10-2.md` (finding 16, LOW, lanes walter and wendy, deferred) and `agoge-2026-11-12.md` (re-observed by walter and wendy).

## Overview

### Problem Statement

`src/lib/buvis/pybase/configuration/loader.py` warns through `logging` (retired `*.local.yaml` twin, world-writable file, unsafe config path). Those lines reach the terminal without the console's ` ⚠ ` marker, so they look like stray output next to the tool's own warnings. The world-writable warning printed twice in sysup in one run.

### Target Users

Every buvis CLI user who meets a config warning.

### Success Metrics

- Each library config warning prints once per process, as ` ⚠ <message>`, in every tool's CLI.
- `src/lib` still emits nothing outside the console adapter and imports no UI framework at import time.

## Functional Decomposition

### Capability: Route library warnings through the console

#### Feature: Logging-to-console bridge in the CLI wrapper

- The `buvis_options` wrapper installs a logging handler for the configuration loggers that renders WARNING records via `console.warning`. Chosen option: agoge option (a).
- Deduplicate repeated identical warnings within one process.

## Structural Decomposition

- `src/lib/buvis/pybase/configuration/click_integration.py` (bridge install)
- `src/lib/buvis/pybase/configuration/loader.py` (warning sites, unchanged API)
- `CHANGELOG.md`

## Implementation Phases

### Phase 1: Design

- [ ] Confirm where the bridge lives so the library invariant holds.

### Phase 2: Core

- [ ] Bridge and dedupe - Acceptance: the evidence warning prints once with ` ⚠ `.
- [ ] CHANGELOG `Fixed` entry.

## Test Strategy

### Critical Scenarios

CliRunner test with a retired twin present: exactly one ` ⚠ Retired config file ...` line. Evidence, verbatim:

```
`braid --dry-run` with twins prints `Retired config file …/config.local.yaml is ignored; move its values to …/.local/.config/buvis/config.yaml`, with no ⚠ marker.
```

## Risks

- A handler on library loggers can double-print if the root logger is also configured; test with `--debug`.
