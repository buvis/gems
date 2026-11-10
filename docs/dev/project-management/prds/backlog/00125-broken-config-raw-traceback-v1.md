---
design: skip
default_model: sonnet
model_tier_rationale: one shared seam in the buvis_options wrapper plus a loader guard; repro given verbatim
---

# Broken config in any layer must not reach the user as a traceback

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 2 of 13, MEDIUM, lanes walter, heidi, trudy.

## Overview

### Problem Statement

Bad YAML, a missing `${VAR}`, a wrong value type or a non-mapping root in any config file reaches the user as a raw Python traceback (`click_integration.py`, `resolver.py`, `loader.py`). `braid --check` then exits 1, which braid.rst defines as "drift", so cron or CI cannot tell broken config from drift. This breaks the AGENTS.md rule "never let raw exceptions reach the user". It predates PRD 00123, but braid's main input is now hand-written YAML.

### Target Users

Anyone hand-editing `buvis-<tool>.yaml` files; automation running `braid --check`.

### Success Metrics

- Each case in the evidence block prints one console error naming the offending file, with no traceback.
- `braid` exits 2 on broken config (braid.rst: exit 2 is an error), `braid --check` exits 1 only for drift.
- `sysup --list` with the same broken file prints the same kind of message.

## Functional Decomposition

### Capability: Config errors at the shared seam

#### Feature: Catch config errors in the `buvis_options` wrapper

- Catch `yaml.YAMLError`, `ConfigurationError` and `MissingEnvVarError`; report through `console` with the file path.
- Reject a non-dict root in `load_yaml` with a `ConfigurationError` naming the file.
- Let a tool choose the exit code; braid maps it to 2. Chosen option: shared seam with caller exit code (agoge option 3).

## Structural Decomposition

- `src/lib/buvis/pybase/configuration/click_integration.py`
- `src/lib/buvis/pybase/configuration/resolver.py`
- `src/lib/buvis/pybase/configuration/loader.py`
- `src/tools/braid/cli.py` (exit-2 mapping)
- `docs/source/configuration.rst`, `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] lib: catch and report config errors in the wrapper with a caller-chosen exit code - Acceptance: no case below prints a traceback.
- [ ] lib: non-dict root raises `ConfigurationError` with the path.
- [ ] braid: map config errors to exit 2.
- [ ] CHANGELOG `Fixed` entry.

## Test Strategy

### Critical Scenarios

Regression tests, failing against current code first. Evidence from the run, verbatim:

```
- `sources: [unclosed` in `~/.local/.config/buvis/buvis-braid.yaml`: `braid --dry-run` gave rc=1 and `yaml.parser.ParserError`. `sysup --list` crashed the same way.
- `${HEIDI_NOPE}` gave `MissingEnvVarError` with a traceback.
- `sources: /abs/path` gave `ConfigurationError: ... sources: Input should be a valid tuple`, rc=1.
- A scalar root gave `AttributeError: 'str' object has no attribute 'items'` at `loader.py:131`.
- braid.rst defines exit 1 as "--check found drift" and exit 2 as an error.
```

## Risks

- It touches the shared library, so every tool's tests must pass.
- Tools other than braid must keep their current exit code unless they opt in.
