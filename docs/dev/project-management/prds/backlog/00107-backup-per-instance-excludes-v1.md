---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription only - the effective-excludes expression, field names and every message are given verbatim; a wrong edit breaks a named test
---

# backup: per-instance excludes

Source: `docs/dev/project-management/intake/processed/00107-backup-multi-source-parallel/discovery.md` (gap added after discovery, decided 2026-10-29: the shared global exclude list cannot serve instances that back up whole home folders).

## Overview

### Problem Statement
Every instance receives the one global exclude list, passed by the runner as `"excludes": list(self._cfg.excludes)`.
`src/tools/backup/runner.py:44`
`BackupInstance` has no exclude field, and `with:` cannot carry excludes either, because the capability `inputs` accept only `source`, `out` and `engine`.
The bundled list drops directories named `build`, `dist`, `out`, `target`, `coverage`, `.cache`, `.npm` everywhere. An instance that backs up a documents tree, a downloads folder or a dot-folder would silently lose any folder with one of those names. Excludes written for one source (`cache` under a kube config) also cannot be scoped to that instance.

### Target Users
The solo operator who runs several `backup` instances over unrelated trees (source code, documents, home config) and needs each tree's exclusions to differ.

### Success Metrics
- `uv run pytest tests/tools/backup/test_instance_excludes.py -q` passes.
- `uv run pytest tests/tools/backup/test_config.py tests/tools/backup/test_tar_archive.py -q` passes unchanged.
- An instance with `inherit_excludes: false` and no `exclude_add` archives a `build/` directory that the global list would drop (`test_inherit_false_keeps_build_dirs`).

## Functional Decomposition

### Capability: Instance-level exclude control
Let each instance trim, extend or ignore the global exclude list.

#### Feature: Instance exclude fields
- **Description**: Three optional instance fields adjust the global list for that instance only.
- **Inputs**: `exclude_add: [pattern]` (default empty), `exclude_remove: [pattern]` (default empty), `inherit_excludes: bool` (default `true`), all at instance level beside `use` and `with`, not inside `with:`.
- **Outputs**: `BackupInstance` carries the three values; unknown instance keys still fail (`extra="forbid"`).
- **Behavior**: Patterns follow the global rules: a pattern without `/` matches a path's basename; a pattern with `/` matches the path relative to the instance `source`.

#### Feature: Effective excludes
- **Description**: One function computes the exclude list an instance runs with.
- **Inputs**: `BackupConfig`, `BackupInstance`.
- **Outputs**: `tuple[str, ...]`.
- **Behavior**: `base = cfg.excludes if instance.inherit_excludes else ()`; drop every pattern in `base` that equals a string in `instance.exclude_remove`; append `instance.exclude_add`; remove duplicates keeping first occurrence (`tuple(dict.fromkeys(...))`). A `exclude_remove` string that is not in `base` is ignored.

#### Feature: Wire into run and inspection
- **Description**: The runner and `--show-excludes` use the effective list.
- **Inputs**: selected instance.
- **Outputs**: the capability receives the effective list as `excludes`; `--show-excludes <instance>` prints it and resolves `.bkpignore` rules from it.
- **Behavior**: the `--show-excludes` header changes from `resolved global excludes for '<name>':` to `resolved excludes for '<name>':` (the list is no longer only global).

## Structural Decomposition

### Repository Structure

```
src/tools/backup/config.py                 # Maps to: Instance exclude fields, Effective excludes
src/tools/backup/runner.py                 # Maps to: Wire into run and inspection
src/tools/backup/cli.py                    # Maps to: Wire into run and inspection
tests/tools/backup/test_instance_excludes.py   # Maps to: all features
docs/source/tools/backup.rst               # Maps to: documentation
CHANGELOG.md                               # Maps to: documentation
```

### Module: config
- **Maps to capability**: Instance-level exclude control
- **Responsibility**: Hold and combine instance exclude settings.
- **Location**: `src/tools/backup/config.py`
- **Exports**:
  - `BackupInstance` - gains `exclude_add`, `exclude_remove`, `inherit_excludes`
  - `effective_excludes(cfg, instance)` - the expression above
- New symbols: `effective_excludes`, `exclude_add`, `exclude_remove`, `inherit_excludes`, `instance.exclude_add`, `instance.exclude_remove`, `test_inherit_false_keeps_build_dirs`

### Module: runner and cli
- **Maps to capability**: Instance-level exclude control
- **Responsibility**: Use `effective_excludes` where `cfg.excludes` is used today.
- **Location**: `src/tools/backup/runner.py`, `src/tools/backup/cli.py`
- **Exports**: none new.

## Dependency Graph

### Foundation Layer (Phase 0)
- **config**: no dependencies; built first.

### Core Layer (Phase 1)
- **runner and cli**: Depends on [config]

### Integration Layer (Phase 2)
- **tests and docs**: Depends on [config, runner and cli]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Fields and combining function exist and validate.

**Tasks**:
- [ ] Add the three fields to `BackupInstance` and `effective_excludes` to `src/tools/backup/config.py` (no deps) - Acceptance: `uv run pytest tests/tools/backup/test_instance_excludes.py -k "effective or inherit or remove or add" -q` passes.

**Exit Criteria**: `effective_excludes` returns the documented tuple for every combination.

### Phase 1: Core
**Goal**: A run and `--show-excludes` use the effective list.

**Tasks**:
- [ ] In `src/tools/backup/runner.py` replace `list(self._cfg.excludes)` by `list(effective_excludes(self._cfg, instance))` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/backup/test_instance_excludes.py -k "runner or build_dirs" -q` passes.
- [ ] In `src/tools/backup/cli.py` make `_show_excludes` print and use `effective_excludes(cfg, instance)` for the named instance (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/backup/test_instance_excludes.py -k show_excludes -q` passes.

**Exit Criteria**: an instance with `inherit_excludes: false` archives a `build/` directory.

### Phase 2: Integration
**Goal**: Documented and fully verified.

**Tasks**:
- [ ] Document the three fields in `docs/source/tools/backup.rst` and add an `Added` line under `[Unreleased]` in `CHANGELOG.md` (depends on: Phase 1) - Acceptance: `rg -c "inherit_excludes" docs/source/tools/backup.rst CHANGELOG.md` prints a count of at least 1 for each file.

**Exit Criteria**: `uv run pytest tests/tools/backup -q` passes; `uv run ruff check src/tools/backup tests/tools/backup` and `uv run mypy src/tools/backup` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: `exclude_add: [scratch]` plus default inherit drops `scratch/` and `node_modules/` → Expected: both absent from the archive.
- **Edge case**: `exclude_remove: [target]` → Expected: `target/` archived, `node_modules/` still dropped.
- **Edge case**: `inherit_excludes: false` with `exclude_add: ["sub/cache"]` → Expected: only `sub/cache` (relative to `source`) dropped, `build/` kept.
- **Error case**: a misspelled instance key such as exclude_ad → Expected: config load fails with `FatalError`.

## Risks

- **Silent keep of junk**: `inherit_excludes: false` archives caches. Mitigation: it is opt-in per instance and visible in `--show-excludes`.
- **Pattern scope confusion**: a `/` pattern is relative to `source`, not its parent. Mitigation: documented in `docs/source/tools/backup.rst` and covered by a test.
