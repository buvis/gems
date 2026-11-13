---
design: skip
default_model: sonnet
model_tier_rationale: ordering change in the shared CLI wrapper; affects every tool's startup
---

# `auto_update: false` in YAML is ignored; every run still checks PyPI

Source: agoge runs `docs/dev/project-management/audit-results/agoge-2026-11-10-2.md` (finding 9, MEDIUM, lane heidi, deferred) and `agoge-2026-11-12.md` (re-observed by heidi). Pre-existing.

## Overview

### Problem Statement

`_run_update_check_once` (`src/lib/buvis/pybase/configuration/click_integration.py`) builds `GlobalSettings()` from the environment only, before YAML is resolved. A user who sets `auto_update: false` in any config file still gets an update check, and possibly an upgrade, on every run. Only `BUVIS_AUTO_UPDATE=false` works. The setting is accepted and then ignored.

### Target Users

Anyone who opts out of updates in config: offline machines, editable dev installs, pinned environments.

### Success Metrics

- With `auto_update: false` in `config.yaml` or `buvis-<tool>.yaml`, a tool run does not touch `updater.json` and makes no PyPI request.
- `BUVIS_AUTO_UPDATE=false` keeps working; env still wins over YAML.

## Functional Decomposition

### Capability: Honour the YAML opt-out

#### Feature: Resolve settings before the update check

- Run the update check after `ConfigResolver.resolve`, using the resolved `auto_update` / `installer`. Chosen option: agoge option (a).
- When config resolution fails, skip the update check (the config error is reported as today).

## Structural Decomposition

- `src/lib/buvis/pybase/configuration/click_integration.py` (`_run_update_check_once`, the `buvis_options` wrapper)
- `docs/source/configuration.rst` (document that `auto_update` works in YAML)
- `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] Move the update check after settings resolution - Acceptance: the evidence case below leaves `updater.json` unchanged.
- [ ] CHANGELOG `Fixed` entry; docs line.

## Test Strategy

### Critical Scenarios

CliRunner test with the installer query stubbed (no network): `auto_update: false` in YAML means the checker is not called; env `false` likewise; `true` calls it. Evidence, verbatim:

```
`auto_update: false` in `config.yaml` or `buvis-braid.yaml`; `braid --dry-run` writes a fresh `updater.json` each run; `BUVIS_AUTO_UPDATE=false` does not.
```

## Risks

- The update check now depends on valid config: a broken config file means no update check that run. Acceptable; the config error is shown.
