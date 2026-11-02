---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: one validation function gains an item-scoped branch; tests and docs follow existing patterns in the same files
---

# backup: allow a bundle `out` under `source` when it lies outside every selected item

Source: hold stub 00117, promoted 2026-11-02 from the deferred finding of batch `202610292344` (ledger `docs/dev/project-management/autopilot/deferred/202610292344-deferred.json`, HIGH, raised against 00109 cycle 1). Depends on nothing open: 00109 and 00110 are done.

## Overview

### Problem Statement
`_reject_out_inside_source` in `src/tools/backup/capabilities/tar_archive.py` refuses any `out` whose resolved path equals or lies under the resolved `source`. Both `TarArchive.run` and `_plan_source` call it before `items` is considered. The guard exists so a whole-tree archive never re-archives its own previous output. A bundle archives only its selected items, so the 00109 headline case is refused although the archive can never contain itself:

```yaml
instances:
  settings:
    use: tar-archive
    with:
      source: "~"
      items: [.gitconfig, .npmrc]
      out: ~/.local/backup/settings.tar.gz
```

Today this fails with `out path ... is inside source ...` for `backup`, `backup --dry-run` and `backup --plan`.

### Target Users
The solo operator who keeps a bundle of home-directory config files and wants the archive under the same home directory.

### Success Metrics
- `uv run pytest tests/tools/backup/test_bundle_items.py tests/tools/backup/test_plan_validation.py -q` passes with the new cases.
- The whole-tree containment tests in `tests/tools/backup/test_tar_archive.py` (`test_out_inside_source_fails_no_archive`, `test_stamped_out_inside_source_fails`) pass unchanged.

## Functional Decomposition

### Capability: Bundle output containment
Decide whether `out` can be written for the archive that will actually be produced.

#### Feature: Item-scoped containment
- **Description**: With `items` set, containment is checked against the selected items instead of `source`.
- **Inputs**: resolved `source`, `out` (parent resolved, name rejoined, as today), the normalized selected items from `_normalize_items`.
- **Outputs**: unchanged `StepResult` / plan row contract.
- **Behavior**:
  - `items` omitted or `null`: unchanged. `out` equal to or under `source` fails with the existing message.
  - `items` set: `out` equal to `source` still fails with the existing message. `out` equal to or under `source / item` for any selected item fails with `out path {out} is inside selected item {source/item}; choose an out path outside the bundle's items`. Any other `out` is allowed, including one under `source`.
  - Items are validated first: an invalid `items` value keeps its existing message and wins over containment, because containment needs the normalized items.
  - `run`, `--dry-run` and `--plan` agree: the plan row is `fail` with the same reason the run would yield, and `run` for the allowed case is `run`.
  - A later run of the allowed case, when `out` already exists under `source`, still succeeds and the previous archive is not a member (it lies outside every item).

## Structural Decomposition

### Repository Structure

```
src/tools/backup/capabilities/tar_archive.py          # Maps to: Item-scoped containment
tests/tools/backup/test_bundle_items.py               # Maps to: run and dry-run cases
tests/tools/backup/test_plan_validation.py            # Maps to: plan cases
docs/source/tools/backup.rst                          # Maps to: documentation
CHANGELOG.md                                          # Maps to: documentation
```

### Module: tar_archive
- **Maps to capability**: Bundle output containment
- **Responsibility**: pick the containment roots (source, or the selected items) and reject `out` inside any of them.
- **Location**: `src/tools/backup/capabilities/tar_archive.py`
- **Exports**: none new; `_reject_out_inside_source` gains the item-scoped branch (or a sibling helper), and both `run` and `_plan_source` normalize items before calling it.

## Dependency Graph

### Foundation Layer (Phase 0)
- **tar_archive**: no dependencies.

### Integration Layer (Phase 1)
- **docs**: depends on [tar_archive].

## Implementation Phases

### Phase 0: Core
**Goal**: The headline bundle case runs, plans and dry-runs; outputs inside a selected item are still refused.

**Tasks**:
- [ ] Add the item-scoped containment branch in `src/tools/backup/capabilities/tar_archive.py` and call it from `run` and `_plan_source` after items are normalized (no deps) - Acceptance: `uv run pytest tests/tools/backup/test_bundle_items.py tests/tools/backup/test_plan_validation.py tests/tools/backup/test_tar_archive.py -q` passes, parametrized over `python-tarfile` and `system-tar` where the file already does so.

**Exit Criteria**: source with `.gitconfig` and `.npmrc`, `items: [.gitconfig, .npmrc]`, `out: <source>/.local/backup/settings.tar.gz` archives exactly the two members in both engines; `items: [.config]` with `out: <source>/.config/x.tar.gz` fails without writing.

### Phase 1: Integration
**Goal**: Documented.

**Tasks**:
- [ ] Add one sentence to the "Selected items" section of `docs/source/tools/backup.rst` stating that a bundle's `out` may lie under `source` but not inside a selected item; add a `Fixed` line under `[Unreleased]` in `CHANGELOG.md` prefixed `**backup**:` (depends on: Phase 0) - Acceptance: `rg -c "selected item" docs/source/tools/backup.rst` prints at least 1 and `rg -c "selected item" CHANGELOG.md` prints at least 1.

**Exit Criteria**: `uv run pytest tests/tools/backup -q` passes; `uv run ruff check src/tools/backup tests/tools/backup` and `uv run mypy src/tools/backup` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: `items: [.gitconfig, .npmrc]`, `out` under `<source>/.local/backup/` → Expected: success, members exactly `.gitconfig` and `.npmrc`, both engines.
- **Happy path, second run**: same config with the archive already present → Expected: success, archive replaced, the archive is not a member.
- **Edge case**: `items: [.config]`, `out: <source>/.config/x.tar.gz` → Expected: failed step naming the selected item, no file written, existing `out` bytes unchanged.
- **Edge case**: `items: [.config]`, `out` equal to `<source>/.config` → Expected: failed step (equality counts as inside).
- **Edge case**: `items` omitted, `out` under `source` → Expected: existing failure and message (unchanged tests).
- **Plan**: `--plan` rows for the happy path and the inside-item case are `run` and `fail` with the run's reason.
- **Error case**: `items: []` with `out` under `source` → Expected: the existing `items must not be empty` message, not a containment message.

## Risks

- **Symlinked items**: an item that is a symlink to a directory holding `out` is archived as a link, never followed, so `out` is not re-archived. No extra check.
- **Stamped outputs**: `out` with `strftime` codes resolves its parent as today; a stamped basename under a selected directory is still rejected because the parent is inside the item.
