---
design: skip
default_model: sonnet
model_tier_rationale: one warning in the loader plus a CHANGELOG marker; repro given verbatim
---

# A leftover buvis-<tool>.local.yaml must warn instead of being ignored silently

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 3 of 13, MEDIUM, lanes wendy, heidi.

## Overview

### Problem Statement

PRD 00122 removed the `buvis-<tool>.local.yaml` sibling twins (`loader.py`). A twin still on disk is now ignored with no message. On the next real `sysup` run, an updater the user turned off runs again. Each machine with a twin hits this once on upgrade, until someone notices. The CHANGELOG states the removal under Removed with "no deprecation period".

### Target Users

Users with an existing `{config,buvis,buvis-<tool>}.local.yaml` in a config search directory.

### Success Metrics

- With the evidence setup below, `sysup --list` prints a warning that names the file and its new path under `~/.local/.config/buvis/`.
- The CHANGELOG entry for 00122 is marked BREAKING with a one-line migration note.

## Functional Decomposition

### Capability: Legacy twin warning

#### Feature: Warn once per twin

- When `{config,buvis,buvis-<tool>}.local.yaml` exists in a search dir, emit one warning through the console naming the old path and the new path.
- Mark the CHANGELOG entry BREAKING and add a migration note. Chosen option: warn plus BREAKING marker (agoge option 1 with option 3's marker).

## Structural Decomposition

- `src/lib/buvis/pybase/configuration/loader.py`
- `CHANGELOG.md`, `docs/source/configuration.rst`

## Implementation Phases

### Phase 1: Core

- [ ] lib: detect legacy twins in search dirs and warn - Acceptance: the repro prints the warning and still loads nothing from the twin.
- [ ] CHANGELOG: BREAKING marker and migration note.

## Test Strategy

### Critical Scenarios

Regression test, failing against current code first. Evidence from the run, verbatim:

```
- `~/.config/buvis/buvis-sysup.local.yaml` contains `commands: {helm: {enabled: false}}`. `sysup --list` still printed `50  helm`, rc=0, with no warning, also under `--log-level debug`.
- The same override in `~/.local/.config/buvis/buvis-sysup.yaml` removes helm.
- A braid twin with `sources+:` was dropped silently.
```

## Risks

- The legacy check adds a path back into a loader that PRD 00122 simplified; remove it after a stated release.
- Noise if a file name collides by chance.
