---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: field names, statuses, messages and the duplicate rule are given verbatim; a wrong edit breaks a named test
---

# backup: --plan preview and once-per-run output resolution

Source: `docs/dev/project-management/intake/processed/00107-backup-multi-source-parallel/discovery.md`. Depends on PRD 00109 (skip state, `items`). PRDs 00111 and 00112 depend on this one.

## Overview

### Problem Statement
`--dry-run` walks every selected tree to count files and bytes, which is slow on a large tree and shows no table of what a run would do. `_expand_stamp` calls `datetime.now()` per instance (`src/tools/backup/capabilities/tar_archive.py:373`), so two instances started seconds apart can resolve a `%H%M%S` stamp differently, and nothing detects two instances that resolve to the same output file. With outputs replaced by later runs, two instances writing one path silently lose one archive, and under parallel execution they race.

### Target Users
The solo operator who checks a multi-instance plan before a scheduled run and wants a safe plan every time.

### Success Metrics
- `uv run pytest tests/tools/backup/test_plan.py -q` passes.
- `--plan` performs no recursive walk: `test_plan_does_not_walk_tree` (patches `os.walk` to raise) passes.
- `test_duplicate_outputs_rejected_before_writing` passes: neither colliding instance writes.

## Functional Decomposition

### Capability: Plan preview
Show what a run would do from cheap filesystem checks only.

#### Feature: Capability plan
- **Description**: Each capability can describe one instance without archiving.
- **Inputs**: the same kwargs as `run` (`source`, `out`, `items`, `engine`, `label`, `now`).
- **Outputs**: `PlanEntry(label, source, out, status, reason, replaces)`; `status` is `run`, `skip` or `fail`; `replaces` is true when `out` already exists.
- **Behavior**: `fail` for unknown engine, `out` inside `source`, `items` invalid per PRD 00109, or `source` not a directory; `skip` for a missing `source` (`source not found: <path>`) or when no selected item exists (`lexists`); otherwise `run`. Uses `lexists`/`is_dir`/`stat` only; never `os.walk`.

#### Feature: `--plan` flag
- **Description**: Prints the plan table and exits without writing.
- **Inputs**: `--plan`, plus the usual `--only` and `--tag` selection and the `--source`/`--out` overrides.
- **Outputs**: one `console.info` line per instance: `<label>  <status>  <source> -> <out>` followed by `  (<reason>)` when a reason exists and `  [replaces existing]` when `replaces`; exit 1 if any entry is `fail`, else 0.
- **Behavior**: `--plan` with `--dry-run` fails: `--plan and --dry-run are mutually exclusive` (exit 1). `--dry-run` is unchanged.

### Capability: Output resolution
Resolve each output once and reject collisions.

#### Feature: Run-wide timestamp
- **Description**: One `now` per run feeds every stamp expansion.
- **Inputs**: `now: datetime`.
- **Outputs**: `_expand_stamp(pattern, now)` uses it; when `now` is absent it falls back to `datetime.now()`.
- **Behavior**: `Runner` takes `now = datetime.now()` once per `run`/`plan` call and passes it as a kwarg.

#### Feature: Duplicate output rejection
- **Description**: Two selected instances may not resolve to one output path.
- **Inputs**: plan entries of the selected instances.
- **Outputs**: for each group sharing a resolved `out`, every instance in the group yields `StepResult(name, success=False, message="output '<out>' is also the output of '<other names, comma separated, sorted>'")` and is not executed; the others run.
- **Behavior**: compared as `os.path.normpath` of the expanded path with `~` expanded; applies to `run`, `--dry-run` and `--plan`.

## Structural Decomposition

### Repository Structure

```
src/tools/backup/step_result.py              # Maps to: Capability plan (PlanEntry)
src/tools/backup/capabilities/__init__.py    # Maps to: Capability plan (protocol)
src/tools/backup/capabilities/tar_archive.py # Maps to: Capability plan, Run-wide timestamp
src/tools/backup/runner.py                   # Maps to: Run-wide timestamp, Duplicate output rejection
src/tools/backup/cli.py                      # Maps to: --plan flag
tests/tools/backup/test_plan.py              # Maps to: all features
docs/source/tools/backup.rst                 # Maps to: documentation
CHANGELOG.md                                 # Maps to: documentation
```

### Module: step_result
- **Maps to capability**: Plan preview
- **Responsibility**: define the plan record.
- **Location**: `src/tools/backup/step_result.py`
- **Exports**: `PlanEntry` (NamedTuple with the six fields above).
- New symbols: `PlanEntry`, `plan`, `now`, `replaces`, `test_plan_does_not_walk_tree`, `test_duplicate_outputs_rejected_before_writing`

### Module: tar_archive and capabilities protocol
- **Maps to capability**: Plan preview, Output resolution
- **Responsibility**: implement `plan`, accept `now`.
- **Location**: `src/tools/backup/capabilities/tar_archive.py`, `src/tools/backup/capabilities/__init__.py`
- **Exports**: `TarArchive.plan(**kwargs) -> PlanEntry`; `Capability` protocol gains `plan`.

### Module: runner
- **Maps to capability**: Output resolution, Plan preview
- **Responsibility**: single `now`, duplicate rejection, `Runner.plan(selected) -> list[PlanEntry]`.
- **Location**: `src/tools/backup/runner.py`

### Module: cli
- **Maps to capability**: Plan preview
- **Responsibility**: `--plan` option and rendering.
- **Location**: `src/tools/backup/cli.py`
- **Exports**: none new.

## Dependency Graph

### Foundation Layer (Phase 0)
- **step_result**: no dependencies; built first.

### Core Layer (Phase 1)
- **tar_archive and capabilities protocol**: Depends on [step_result]
- **runner**: Depends on [step_result, tar_archive and capabilities protocol]

### Integration Layer (Phase 2)
- **cli**: Depends on [runner]

## Implementation Phases

### Phase 0: Foundation
**Goal**: The plan record exists.

**Tasks**:
- [ ] Add `PlanEntry` to `src/tools/backup/step_result.py` (no deps) - Acceptance: `uv run pytest tests/tools/backup/test_plan.py -k plan_entry -q` passes.

**Exit Criteria**: `PlanEntry` importable with the six fields.

### Phase 1: Core
**Goal**: Capability plans, one `now`, duplicates rejected.

**Tasks**:
- [ ] Add `TarArchive.plan`, the `plan` member of `Capability`, and the `now` parameter of `_expand_stamp` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/backup/test_plan.py -k "capability or stamp or walk" -q` passes.
- [ ] Add `Runner.plan`, the single per-run `now`, and duplicate rejection in `Runner.run` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/backup/test_plan.py -k "runner or duplicate" -q` passes.

**Exit Criteria**: two instances with one `out` both fail without writing.

### Phase 2: Integration
**Goal**: `--plan` works and is documented.

**Tasks**:
- [ ] Add `--plan` to `src/tools/backup/cli.py` with the mutual-exclusion check (depends on: Phase 1) - Acceptance: `uv run pytest tests/tools/backup/test_plan.py -k cli -q` passes.
- [ ] Document `--plan` in `docs/source/tools/backup.rst`; add an `Added` line under `[Unreleased]` in `CHANGELOG.md` (depends on: Phase 1) - Acceptance: `rg -c "\-\-plan" docs/source/tools/backup.rst CHANGELOG.md` prints a count of at least 1 for each file.

**Exit Criteria**: `uv run pytest tests/tools/backup -q` passes; `uv run ruff check src/tools/backup tests/tools/backup` and `uv run mypy src/tools/backup` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: three instances, one with a missing source → Expected: lines `run`, `run`, `skip (source not found: …)`; no file written; exit 0.
- **Edge case**: existing output → Expected: line ends `[replaces existing]`.
- **Edge case**: `%H%M%S` stamp, two instances → Expected: identical timestamp in both resolved names.
- **Error case**: two instances, one `out` → Expected: both `fail` in `--plan`, both failed steps in a run, nothing written.
- **Error case**: `--plan --dry-run` → Expected: exit 1 with the documented message.

## Risks

- **Plan drifts from reality**: a plan is a point-in-time preview. Mitigation: documented; execution rechecks everything.
- **Protocol change**: adding `plan` to `Capability` breaks any other capability. Mitigation: `TarArchive` is the only registered capability (`src/tools/backup/capabilities/__init__.py`).
