---
design: skip
default_model: sonnet
model_tier_rationale: one loader seam in sysup, but it must agree with the shared resolver's key rules
---

# sysup crashes or dumps raw pydantic errors on valid-looking config

Source: agoge runs `docs/dev/project-management/audit-results/agoge-2026-11-10-2.md` (finding 8, MEDIUM, lane heidi, deferred) and `agoge-2026-11-12.md` (re-observed by heidi and walter). Pre-existing: reproduces at `gems-v0.20.0`.

## Overview

### Problem Statement

sysup validates its plan (`SysupConfig`) separately from its runtime settings, and the two disagree. Three symptoms share that seam in `src/tools/sysup/config.py`:

- List directives on plan keys (`commands+:`, `commands-:`, `expiry-:`) crash with a Python traceback.
- Keys the shared resolver accepts (`debug`, `log_level`, `auto_update`, and any other tool's key in a shared `config.yaml`) make `SysupConfig` fail with `Extra inputs are not permitted`. backup's plan loader has the same shape by file name.
- Type errors print a raw pydantic dump with an `errors.pydantic.dev` URL and no file name.

If unchanged, sysup users meet tracebacks and unreadable errors whenever a shared config file carries keys for other tools. Stable.

### Target Users

sysup users who keep shared settings in `config.yaml` / `buvis.yaml` or use list directives in `buvis-sysup.yaml`.

### Success Metrics

- `commands-: [x]` in `buvis-sysup.yaml` either applies or prints ` ✘ <file>: <reason>`, never a traceback.
- `debug: true` (or another tool's top-level key) in a shared file does not stop `sysup --list`.
- A type error names the file and field in one console line, without a pydantic URL.

## Functional Decomposition

### Capability: Plan load agrees with the settings resolver

#### Feature: Project and render

- Before validation, project the merged layers onto `SysupConfig`'s own keys (as `src/tools/backup/config.py` does), so shared and global keys are not plan errors. Chosen option: agoge option (a).
- Apply list directives through `ConfigurationLoader.merge_configs` the same way the resolver does, or reject them with a clean `ConfigurationError` naming the file.
- Catch `ValidationError` / `ConfigurationError` at the CLI boundary and render them like the resolver's errors (file and field, no URL).

## Structural Decomposition

- `src/tools/sysup/config.py` (`load_config`, `SysupConfig`)
- `src/tools/sysup/cli.py`
- `src/tools/backup/config.py` (same projection check)
- `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] sysup plan load projects onto plan keys and renders errors - Acceptance: the three evidence cases below no longer traceback or dump pydantic URLs.
- [ ] backup: confirm the same shared-key case passes; fix the same way if not.
- [ ] CHANGELOG `Fixed` entry.

## Test Strategy

### Critical Scenarios

Regression tests through the sysup CLI, failing against current code first. Evidence, verbatim:

```
`commands-: [x]` -> traceback ending `ConfigurationError: Merge directive on key 'commands' requires a list value`
`debug: true` -> ` ✘ invalid sysup configuration ... Extra inputs are not permitted`
`prime: 5` -> raw pydantic block
`bim:` section in ~/.local/.config/buvis/config.yaml -> `sysup --list` rc=1 ` ✘ invalid sysup configuration: 1 validation error for SysupConfig / bim / Extra inputs are not permitted`
```

## Risks

- Touches sysup's plan contract; a key that was a plan error becomes silently ignored after projection. Keep the unknown-key check for `buvis-sysup.yaml` itself.
