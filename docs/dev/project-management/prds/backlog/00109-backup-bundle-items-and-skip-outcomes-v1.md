---
catchup: skip
design: skip
default_model: opus
model_tier_rationale: invented selection algorithm and a new StepResult/exit contract consumed by three later PRDs
---

# backup: bundle items, skipped outcomes, replace-after-complete

Source: `docs/dev/project-management/intake/processed/00107-backup-multi-source-parallel/discovery.md`. Decisions of 2026-10-29 override the discovery: no no-clobber and no `--force` (an existing output is replaced, only after the new archive is complete), and a missing source root is a skip, not a failure. Depends on PRD 00107 (both edit `src/tools/backup/capabilities/tar_archive.py` and `src/tools/backup/runner.py`).

## Overview

### Problem Statement
`tar-archive` takes one source directory, checked with `source.is_dir()`.
`src/tools/backup/capabilities/tar_archive.py:107`
So a few loose files under one parent (for example `.gitconfig` and `.npmrc` under `$HOME`) cannot go into one archive. A missing source is a failed step: `yield StepResult(label, success=False, message=f"source not found: {source}")`.
`src/tools/backup/capabilities/tar_archive.py:108`
A path that does not exist cannot be backed up, so a scheduled run should not turn red for it. `StepResult` has only `success` true or false, so "nothing to do" has no representation.
The existing atomic publication (`os.replace` in both archive writers) already keeps a prior output intact until a new one is complete; no test pins that.

### Target Users
The solo operator who runs scheduled backups of several optional trees and bundles of config files.

### Success Metrics
- `uv run pytest tests/tools/backup/test_bundle_items.py -q` passes.
- `uv run pytest tests/tools/backup/test_skip_outcomes.py -q` passes.
- `uv run pytest tests/tools/backup/test_replace_after_complete.py -q` passes for both engines.
- Existing whole-tree archives keep their member names (`uv run pytest tests/tools/backup/test_tar_archive.py -q` passes after the one deliberate test edit below).

## Functional Decomposition

### Capability: Bundle selection
Archive chosen files and directories under one base into one archive.

#### Feature: `items` input
- **Description**: Optional `items` list under `source` selects what is archived.
- **Inputs**: `items: list[str]` (literal relative paths, no globs). Omitted means whole tree, unchanged.
- **Outputs**: archive whose member names are relative to `source` (no `source.name` prefix); whole-tree member names unchanged (relative to `source.parent`).
- **Behavior**:
  - Each item is normalized with posixpath.normpath. An item that is empty, absolute, equal to `.` or starts with `..` fails the step: `invalid item '<item>': must be a relative path inside the source`. An explicitly empty list fails: `items must not be empty`.
  - An item that equals, or lies under, another selected item is dropped; duplicates collapse.
  - If any parent component of an item (every component except the last, joined onto `source`) is a symlink, the step fails: `item '<item>' passes through symlink '<component>'`. A final component that is a symlink is archived as the link, never followed.
  - A file item is one member; a directory item is walked with the existing rules, including empty directories, symlinks as links, and `.bkpignore` layering. Parent directories of an item (`.config` for `.config/tool`) are not added as members.
  - Exclusions apply to items: patterns match against paths relative to `source` (for `/` patterns) or basenames. `.bkpignore` rules from `source` down to the item's parent directory apply (`resolve_state_for_path` in `src/tools/backup/shared/bkpignore.py`). An item that the rules exclude is not archived and is not an error.
  - Reading failures (permission denied, file vanishing after selection) fail the step, never count as missing.

#### Feature: Item presence tolerance
- **Description**: Absent items are reported, present ones archived.
- **Inputs**: selected items.
- **Outputs**: success message ends `; missing items: a, b` when any item is absent (`os.path.lexists` false on `source/item`); when every selected item is absent, or every present item is excluded, the result is a skip (below) and no archive is written.
- **Behavior**: absence is decided by `lexists` only; any other `OSError` during the walk fails the step.

### Capability: Skipped outcomes
Represent "nothing to back up" as a successful, explicit result.

#### Feature: Skip state and reasons
- **Description**: `StepResult` gains `skipped: bool = False`; a skip is `success=True, skipped=True` with the reason in `message`.
- **Inputs**: `source` path.
- **Outputs**: a missing `source` yields a skip with message `source not found: <path>`; a `source` that exists but is not a directory still fails: `source is not a directory: <path>`.
- **Behavior**: a skip never writes, never deletes, and never touches an existing output.

#### Feature: Run summary and exit status
- **Description**: The CLI shows how every step ended and sets the exit code.
- **Inputs**: all `StepResult` of the run.
- **Outputs**: skipped steps render with `console.warning`; after all steps one `console.info` line `archived A, skipped S, failed F` (`previewed` instead of `archived` under `--dry-run`). Exit 0 when F is 0, including an all-skipped run; exit 1 otherwise.
- **Behavior**: counts are by step: failed is `not success`, skipped is `skipped`, archived is the rest.

### Capability: Replace-after-complete contract
An existing output is replaced only by a finished archive.

#### Feature: Pinned publication contract
- **Description**: Tests and documentation fix the behavior already provided by atomic publication.
- **Inputs**: a pre-existing `out` file.
- **Outputs**: after a successful run `out` holds the new archive; after a failed or skipped run `out` holds its previous bytes; no temp file remains.
- **Behavior**: no code change expected. Premise: both writers publish through `os.replace(tmp_path, out)` (`rg -c "os.replace" src/tools/backup/capabilities/tar_archive.py` prints at least 2 at execution time); if a writer does not, fix it to write a sibling temp file and replace only on success.

## Structural Decomposition

### Repository Structure

```
src/tools/backup/step_result.py                       # Maps to: Skip state and reasons
src/tools/backup/capabilities/tar_archive.py          # Maps to: items input, presence tolerance, skip, publication
src/tools/backup/cli.py                               # Maps to: Run summary and exit status
tests/tools/backup/test_bundle_items.py               # Maps to: Bundle selection
tests/tools/backup/test_skip_outcomes.py              # Maps to: Skipped outcomes
tests/tools/backup/test_replace_after_complete.py     # Maps to: Replace-after-complete contract
tests/tools/backup/test_tar_archive.py                # Maps to: one deliberate test edit
tests/tools/backup/test_backup_cli.py                 # Maps to: summary rendering
docs/source/tools/backup.rst                          # Maps to: documentation
CHANGELOG.md                                          # Maps to: documentation
```

### Module: step_result
- **Maps to capability**: Skipped outcomes
- **Responsibility**: carry the skip flag.
- **Location**: `src/tools/backup/step_result.py`
- **Exports**: `StepResult(label, success, message="", archive=None, skipped=False)`.

### Module: tar_archive
- **Maps to capability**: Bundle selection, Skipped outcomes, Replace-after-complete contract
- **Responsibility**: select items, report presence, skip, publish.
- **Location**: `src/tools/backup/capabilities/tar_archive.py`
- **Exports**: `TarArchive` (`inputs` gains `items`), `WalkResult` (gains `missing`).
- New symbols: `items`, `missing`, `skipped`, `_select_items`, `test_missing_source_is_skipped`

### Module: cli
- **Maps to capability**: Skipped outcomes
- **Responsibility**: render skips and the summary.
- **Location**: `src/tools/backup/cli.py`
- **Exports**: none new.

## Dependency Graph

### Foundation Layer (Phase 0)
- **step_result**: no dependencies; built first.

### Core Layer (Phase 1)
- **tar_archive**: Depends on [step_result]

### Integration Layer (Phase 2)
- **cli and docs**: Depends on [step_result, tar_archive]

## Implementation Phases

### Phase 0: Foundation
**Goal**: A skip can be expressed.

**Tasks**:
- [ ] Add `skipped: bool = False` to `StepResult` in `src/tools/backup/step_result.py` (no deps) - Acceptance: `uv run pytest tests/tools/backup/test_skip_outcomes.py -k step_result -q` passes.

**Exit Criteria**: `StepResult("x", True, "m", skipped=True).skipped` is true and positional construction elsewhere still works.

### Phase 1: Core
**Goal**: The archive capability selects items, skips, and publishes as specified.

**Tasks**:
- [ ] Skip a missing `source` and fail a non-directory `source` in `src/tools/backup/capabilities/tar_archive.py` (depends on: Phase 0). Premise: `test_missing_source_fails_cleanly` exists once in `tests/tools/backup/test_tar_archive.py` (`rg -c "def test_missing_source_fails_cleanly" tests/tools/backup/test_tar_archive.py` prints 1) and `tests/tools/backup/test_backup_cli.py` uses a failed `StepResult("a", False, "a failed: source not found")` only as fixture text; if the premise fails, skip the test edit and report. Replace that test with `test_missing_source_is_skipped` asserting `success is True`, `skipped is True` and `"source not found" in message` - Acceptance: `uv run pytest tests/tools/backup/test_skip_outcomes.py tests/tools/backup/test_tar_archive.py -q` passes.
- [ ] Add `items` selection (`_select_items`, validation, de-duplication, symlink-parent rejection, exclusions, `missing`) and base-relative member names to both writers by passing the member base into `_write_archive` and `_write_archive_system_tar` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/backup/test_bundle_items.py -q` passes, parametrized over `python-tarfile` and `system-tar`.
- [ ] Add `tests/tools/backup/test_replace_after_complete.py` (depends on: Phase 0) - Acceptance: it passes for both engines; failure case forces the writer to raise and asserts the prior bytes of `out` are unchanged and no `*.tmp` sibling remains.

**Exit Criteria**: a bundle of two files under a base archives them at base-relative names; an absent item is reported; an absent source skips.

### Phase 2: Integration
**Goal**: The run reports and exits as specified, and the behavior is documented.

**Tasks**:
- [ ] Render skipped steps with `console.warning`, print the summary line, keep exit 1 only on failure in `src/tools/backup/cli.py` (depends on: Phase 1) - Acceptance: `uv run pytest tests/tools/backup/test_backup_cli.py -k "skip or summary" -q` passes, including an all-skipped run exiting 0 and a mixed run exiting 1.
- [ ] Document `items`, skip semantics and replace-after-complete in `docs/source/tools/backup.rst`; add `Added` and `Changed` lines under `[Unreleased]` in `CHANGELOG.md` (depends on: Phase 1) - Acceptance: `rg -c "items" docs/source/tools/backup.rst` prints at least 1 and `rg -c "skipped" CHANGELOG.md` prints at least 1.

**Exit Criteria**: `uv run pytest tests/tools/backup -q` passes; `uv run ruff check src/tools/backup tests/tools/backup` and `uv run mypy src/tools/backup` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: base with `.gitconfig`, `.config/tool/a`, items `[.gitconfig, .config/tool]` → Expected: members `.gitconfig`, `.config/tool`, `.config/tool/a`; nothing else; no `.config` member.
- **Edge case**: one of three items absent → Expected: success, archive of two, message lists the missing one.
- **Edge case**: all items absent → Expected: `skipped`, no archive, existing `out` unchanged.
- **Edge case**: nested `items` `[a, a/b]` → Expected: `a` walked once.
- **Edge case**: item inside a dir symlink (`link/x`) → Expected: failed step naming the symlink.
- **Edge case**: item matching a global exclude → Expected: not archived, no error.
- **Error case**: `items: []`, `items: ["/etc"]`, `items: ["../x"]` → Expected: failed step with the documented message.
- **Error case**: unreadable item → Expected: failed step, no archive.
- **Contract**: existing `out` + failing write → Expected: prior bytes intact. Existing `out` + success → Expected: new archive. Missing source + existing `out` → Expected: skip, prior bytes intact.

## Risks

- **Misconfiguration hidden as success**: a mistyped source or item skips quietly. Mitigation: every skip prints a warning with its reason and the summary counts skips; the operator chose this (a missing path cannot be backed up).
- **Disconnected drive**: a missing mount skips instead of failing. Mitigation: same warning and count; previous outputs are never touched.
- **Same-name outputs**: replacing an output with the same name loses the older copy if two instances resolve to one path. Mitigation: covered by PRD 00110 (duplicate-output rejection).
