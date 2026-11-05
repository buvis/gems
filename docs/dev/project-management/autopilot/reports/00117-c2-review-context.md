# Review Context

## Completed Tasks

| ID | Task | Status | Commit | Description | Shared with |
|----|------|--------|--------|-------------|-------------|
| 1 | 00117-backup-bundle-out-under-source-v1-c1 | completed |  |  |  |
| 2 | [D1] src/tools/backup/capabilities/tar_archive.py | completed |  | ### Findings (verbatim) - 🟡 src/tools/backup/capabilities/tar_archive.py:285: Items are normalized twice in both run and plan. Normalize once and pass the selected paths to containment and selection. (found by: ALICE, BOB) - 🟠 src/tools/backup/capabilities/tar_archive.py:299: The new item comparison can allow output inside a selected directory on case-insensitive filesystems: items ["Config"] and out "<source>/config/archive.tar.gz" compare unequal lexically but address the same directory. Previously the whole-source guard rejected this configuration. Compare filesystem identity for existing ancestors while preserving final-symlink semantics; add coverage for both engines and every mode. (found by: BOB) |  |

## Code Changes

### Changed Files
_Diff scope: incremental review (changes since 5ae5c53e49ad95d94562b60df99aa272e0772cc5)_

```
 CHANGELOG.md                                       |   8 +-
 .../autopilot/autocodex-metrics.jsonl              |   3 +
 .../3636b45977914160acbe519907b52873.jsonl         |  44 ++
 .../3636b45977914160acbe519907b52873.prompt.md     | 280 ++++++++++
 .../3636b45977914160acbe519907b52873.stderr        |   8 +
 .../4c8f75584f754951833be5d6cc02b84e.jsonl         | 296 ++++++++++
 .../4c8f75584f754951833be5d6cc02b84e.prompt.md     | 280 ++++++++++
 .../4c8f75584f754951833be5d6cc02b84e.stderr        |   8 +
 .../7217412772284e13b5abc28b805b8649.jsonl         | 173 ++++++
 .../7217412772284e13b5abc28b805b8649.prompt.md     | 280 ++++++++++
 .../7217412772284e13b5abc28b805b8649.stderr        |   8 +
 .../autopilot/dispatch-metrics.jsonl               |  44 ++
 .../autopilot/ledger/dispatch-metrics.jsonl        |  44 ++
 .../autopilot/ledger/loop-metrics.jsonl            |   1 +
 .../autopilot/loop-metrics.jsonl                   |   1 +
 ...-out-under-source-v1-implementation-models.json | 140 +++++
 ...le-out-under-source-v1-implementation-models.md |  70 +++
 ...e-openai-05627034e2164adb8453dc303f166cce.jsonl |  95 ++++
 ...-openai-05627034e2164adb8453dc303f166cce.stderr |   8 +
 .../autopilot/reports/00117-c1-alice-openai.txt    |  16 +
 .../reports/00117-c1-alice-openai.txt.receipt.json |  19 +
 ...e-openai-69b368826f68434984e0342a5171a23e.jsonl |  37 ++
 ...-openai-69b368826f68434984e0342a5171a23e.stderr |   8 +
 .../autopilot/reports/00117-c1-blake-openai.txt    |  21 +
 .../reports/00117-c1-blake-openai.txt.receipt.json |  19 +
 ...b-openai-ffb5347fbe96461392c855d924c2c312.jsonl |   5 +
 ...-openai-ffb5347fbe96461392c855d924c2c312.stderr |   0
 .../autopilot/reports/00117-c1-bob-openai.txt      |  28 +
 .../reports/00117-c1-bob-openai.txt.receipt.json   |  19 +
 .../autopilot/reports/00117-c1-full-suite.log      | 608 +++++++++++++++++++++
 .../reports/00117-c1-implementation-models.json    |  96 ++++
 .../reports/00117-c1-implementation-models.md      |  66 +++
 .../reports/00117-c1-rework-full-suite.log         | 142 +++++
 .../audit-evidence-rows.json                       |  34 ++
 .../00117-c1-rework-model-evidence/correlation.md  |   7 +
 .../00117-c1-rework-model-evidence/manifest.json   |  18 +
 .../narrow-verification.txt                        |   5 +
 .../00117-c1-rework-model-evidence/pat-1.txt       |   9 +
 .../00117-c1-rework-model-evidence/pat-2.txt       |   9 +
 .../00117-c1-rework-model-evidence/pat-prompt-1.md | 397 ++++++++++++++
 .../00117-c1-rework-model-evidence/pat-prompt-2.md | 120 ++++
 ...3-32-01a1ab29-e892-7f21-85d0-323f9bb5be45.jsonl | 105 ++++
 ...6-05-01a1ab2c-3cdb-75a1-a423-c4dcb707ec13.jsonl | 131 +++++
 .../autopilot/reports/00117-c1-rework.md           |  24 +
 .../autopilot/reports/00117-c1-verification.json   |  15 +
 .../00117-recovery-evidence/coordinator.jsonl      |  16 +
 .../reports/00117-recovery-evidence/dispatch.jsonl |   4 +
 .../reports/00117-recovery-evidence/ivan.jsonl     |  10 +
 .../reports/00117-recovery-evidence/ivan.meta.json |   1 +
 .../reports/00117-recovery-evidence/manifest.json  | 253 +++++++++
 .../00117-recovery-evidence/original-review-1.md   |  63 +++
 .../00117-recovery-evidence/paused-state.json      |  72 +++
 .../00117-recovery-evidence/resumed-state.json     |  77 +++
 .../reports/00117-recovery-evidence/tess.jsonl     |  10 +
 .../reports/00117-recovery-evidence/tess.meta.json |   1 +
 .../00117-backup-bundle-out-under-source-v1.md     |   0
 ...7-backup-bundle-out-under-source-v1-ledger.json |  42 ++
 ...7-backup-bundle-out-under-source-v1-review-1.md | 154 ++++++
 docs/source/tools/backup.rst                       |  10 +
 pyproject.toml                                     |   2 +-
 src/tools/backup/capabilities/tar_archive.py       |  76 ++-
 src/tools/sysup/default.yaml                       |   7 +
 tests/tools/backup/test_bundle_case_containment.py | 183 +++++++
 tests/tools/backup/test_bundle_items.py            | 202 +++++++
 tests/tools/backup/test_plan_validation.py         | 162 ++++++
 tests/tools/sysup/test_default_config.py           |  13 +-
 uv.lock                                            |   2 +-
 67 files changed, 5082 insertions(+), 27 deletions(-)
```

### Diff Content
Full diff available at: /Users/bob/git/src/github.com/buvis/gems/docs/dev/tmp/review-diff-00117-c2.diff

(5661 lines)

## PRD Requirements

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

## Mechanical facts (computed, do not re-count)

Function line counts from `ast`. Cite these for countable claims; a
finding that contradicts this block is discarded at the review gate.

- `CHANGELOG.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/3636b45977914160acbe519907b52873.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/3636b45977914160acbe519907b52873.prompt.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/3636b45977914160acbe519907b52873.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/4c8f75584f754951833be5d6cc02b84e.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/4c8f75584f754951833be5d6cc02b84e.prompt.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/4c8f75584f754951833be5d6cc02b84e.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/7217412772284e13b5abc28b805b8649.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/7217412772284e13b5abc28b805b8649.prompt.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/7217412772284e13b5abc28b805b8649.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/dispatch-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/ledger/dispatch-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/ledger/loop-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/loop-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-backup-bundle-out-under-source-v1-implementation-models.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-backup-bundle-out-under-source-v1-implementation-models.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-alice-openai-05627034e2164adb8453dc303f166cce.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-alice-openai-05627034e2164adb8453dc303f166cce.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-alice-openai.txt` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-alice-openai.txt.receipt.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-blake-openai-69b368826f68434984e0342a5171a23e.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-blake-openai-69b368826f68434984e0342a5171a23e.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-blake-openai.txt` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-blake-openai.txt.receipt.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-bob-openai-ffb5347fbe96461392c855d924c2c312.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-bob-openai-ffb5347fbe96461392c855d924c2c312.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-bob-openai.txt` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-bob-openai.txt.receipt.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-full-suite.log` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-implementation-models.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-implementation-models.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-full-suite.log` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/audit-evidence-rows.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/correlation.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/manifest.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/narrow-verification.txt` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/pat-1.txt` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/pat-2.txt` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/pat-prompt-1.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/pat-prompt-2.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/rollout-2026-11-05T11-03-32-01a1ab29-e892-7f21-85d0-323f9bb5be45.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework-model-evidence/rollout-2026-11-05T11-06-05-01a1ab2c-3cdb-75a1-a423-c4dcb707ec13.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-rework.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-c1-verification.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/coordinator.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/dispatch.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/ivan.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/ivan.meta.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/manifest.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/original-review-1.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/paused-state.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/resumed-state.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/tess.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00117-recovery-evidence/tess.meta.json` — skipped (non-python)
- `docs/dev/project-management/prds/wip/00117-backup-bundle-out-under-source-v1.md` — skipped (non-python)
- `docs/dev/project-management/reviews/00117-backup-bundle-out-under-source-v1-ledger.json` — skipped (non-python)
- `docs/dev/project-management/reviews/00117-backup-bundle-out-under-source-v1-review-1.md` — skipped (non-python)
- `docs/source/tools/backup.rst` — skipped (non-python)
- `pyproject.toml` — skipped (non-python)
- `src/tools/backup/capabilities/tar_archive.py`
  - `_check_cancel` — line 37, 3 lines
  - `_emit_progress` — line 42, 4 lines
  - `_start_archive_progress` — line 48, 22 lines
  - `_start_archive_progress.on_bytes` — line 56, 7 lines
  - `_start_archive_progress.on_finalize` — line 64, 4 lines
  - `WalkResult.__init__` — line 84, 11 lines
  - `WalkResult.file_count` — line 97, 2 lines
  - `TarArchive.inputs` — line 114, 2 lines
  - `TarArchive.plan` — line 117, 16 lines
  - `TarArchive.run` — line 134, 36 lines
  - `TarArchive._run_validated` — line 171, 43 lines
  - `TarArchive._dry_run_result` — line 216, 12 lines
  - `TarArchive._archive_result` — line 230, 39 lines
  - `TarArchive._archive_result.finalize_once` — line 247, 4 lines
  - `_same_path` — line 271, 8 lines
  - `_reject_out_inside_source` — line 281, 39 lines
  - `_no_items_message` — line 322, 3 lines
  - `_plan_items` — line 327, 9 lines
  - `_source_kind` — line 338, 11 lines
  - `_plan_source` — line 351, 18 lines
  - `_item_present` — line 371, 7 lines
  - `_normalize_items` — line 380, 18 lines
  - `_select_items` — line 400, 38 lines
  - `_walk_tree` — line 440, 70 lines
  - `_raise_walk_error` — line 512, 8 lines
  - `_collect_applied` — line 522, 8 lines
  - `_write_archive` — line 532, 42 lines
  - `_write_archive_system_tar` — line 576, 49 lines
  - `_run_system_tar` — line 627, 32 lines
  - `_cleanup_tar_process` — line 661, 17 lines
  - `_parse_inputs` — line 680, 9 lines
  - `_missing_input` — line 691, 5 lines
  - `resolve_paths` — line 698, 9 lines
  - `_require_str` — line 709, 3 lines
  - `_expand_stamp` — line 714, 10 lines
  - `_as_str_tuple` — line 726, 4 lines
- `src/tools/sysup/default.yaml` — skipped (non-python)
- `tests/tools/backup/test_bundle_case_containment.py`
  - `engine` — line 13, 2 lines
  - `mode` — line 18, 2 lines
  - `_outcome` — line 22, 8 lines
  - `_snapshot` — line 32, 7 lines
  - `_case_alias` — line 41, 5 lines
  - `TestBundleCaseContainment.test_output_identity_permission_error_fails_without_replacing_output` — line 50, 27 lines
  - `TestBundleCaseContainment.test_output_identity_permission_error_fails_without_replacing_output.denied_lstat` — line 65, 4 lines
  - `TestBundleCaseContainment.test_case_alias_of_selected_directory_rejects_output_without_changes` — line 80, 21 lines
  - `TestBundleCaseContainment.test_near_miss_sibling_allows_output_and_keeps_every_selected_item` — line 103, 25 lines
  - `TestBundleCaseContainment.test_final_symlink_items_allow_output_in_target_without_archiving_target_contents` — line 130, 30 lines
  - `TestBundleCaseContainment.test_invalid_items_take_precedence_over_output_containment` — line 169, 15 lines
- `tests/tools/backup/test_bundle_items.py`
  - `engine` — line 17, 2 lines
  - `_tree` — line 21, 5 lines
  - `_run` — line 28, 13 lines
  - `_members` — line 43, 3 lines
  - `_runner` — line 48, 19 lines
  - `TestBundleItems.test_selected_files_and_directory_use_base_relative_names` — line 70, 24 lines
  - `TestBundleItems.test_normalization_deduplicates_selected_ancestors_without_prefix_collisions` — line 95, 13 lines
  - `TestBundleItems.test_items_are_literal_paths_without_glob_expansion` — line 109, 7 lines
  - `TestBundleItems.test_invalid_item_fails_without_replacing_output` — line 118, 10 lines
  - `TestBundleItems.test_traversal_items_are_rejected` — line 130, 8 lines
  - `TestBundleItems.test_dot_dot_prefixed_literal_names_are_valid_items` — line 139, 13 lines
  - `TestBundleItems.test_none_items_archives_whole_tree_like_omitted_items` — line 153, 13 lines
  - `TestBundleItems.test_non_list_items_fail_with_exact_message` — line 168, 11 lines
  - `TestBundleItems.test_explicitly_empty_items_fails` — line 180, 9 lines
  - `TestBundleItems.test_missing_items_are_listed_while_present_items_are_archived` — line 190, 9 lines
  - `TestBundleItems.test_parent_symlink_fails_while_final_symlinks_are_preserved` — line 200, 21 lines
  - `TestBundleItems.test_excludes_match_base_relative_paths_and_basename_without_substring_matching` — line 222, 21 lines
  - `TestBundleItems.test_ancestor_and_directory_bkpignore_layers_apply_to_selected_items` — line 244, 28 lines
  - `TestBundleItems.test_unreadable_selected_file_fails_instead_of_skipping` — line 273, 33 lines
  - `TestBundleItems.test_unreadable_selected_file_fails_instead_of_skipping.denied` — line 287, 6 lines
  - `TestBundleItems.test_unreadable_selected_file_fails_instead_of_skipping.denied_stat` — line 294, 4 lines
  - `TestBundleItems.test_file_vanishing_after_presence_check_fails_instead_of_skipping` — line 307, 23 lines
  - `TestBundleItems.test_file_vanishing_after_presence_check_fails_instead_of_skipping.vanish` — line 318, 5 lines
  - `_home` — line 332, 15 lines
  - `_source_msg` — line 349, 2 lines
  - `_item_msg` — line 353, 2 lines
  - `_names` — line 357, 2 lines
  - `TestBundleOutContainment.test_out_under_source_outside_every_item_archives_only_items` — line 363, 11 lines
  - `TestBundleOutContainment.test_rerun_with_existing_out_under_source_succeeds_without_self_member` — line 375, 13 lines
  - `TestBundleOutContainment.test_out_equal_to_or_inside_selected_item_fails_without_writing` — line 400, 15 lines
  - `TestBundleOutContainment.test_out_equal_to_source_keeps_source_message_with_items` — line 417, 9 lines
  - `TestBundleOutContainment.test_out_under_source_near_an_item_but_outside_it_is_allowed` — line 437, 11 lines
  - `TestBundleOutContainment.test_whole_tree_out_under_source_keeps_source_message` — line 450, 11 lines
  - `TestBundleOutContainment.test_invalid_items_win_over_containment` — line 471, 7 lines
  - `TestBundleOutContainment.test_symlinked_item_is_archived_as_link_so_out_beside_target_is_allowed` — line 479, 12 lines
  - `TestBundleOutContainment.test_out_reached_through_symlinked_parent_is_judged_by_its_real_location` — line 492, 10 lines
  - `TestBundleOutContainment.test_stamped_out_basename_under_selected_directory_is_rejected` — line 503, 8 lines
  - `TestBundleOutContainment.test_stamped_out_basename_outside_items_is_allowed` — line 512, 9 lines
  - `TestBundleOutContainment.test_relative_out_is_judged_against_the_working_directory` — line 523, 8 lines
- `tests/tools/backup/test_plan_validation.py`
  - `_source` — line 21, 6 lines
  - `_invoke` — line 29, 10 lines
  - `_assert_archive` — line 41, 8 lines
  - `_snapshot` — line 51, 2 lines
  - `test_empty_engine_matches_omitted_python_engine` — line 58, 26 lines
  - `test_empty_paths_fail_without_using_cwd_or_changing_artifacts` — line 90, 29 lines
  - `_mixed_config` — line 121, 16 lines
  - `test_runner_keeps_missing_inputs_distinct_from_collisions_and_executes_independent_instances` — line 140, 40 lines
  - `test_engine_lookalikes_remain_rejected_without_archive_effects` — line 185, 17 lines
  - `test_fatal_archive_errors_follow_interface_contract_with_empty_default_engine` — line 206, 23 lines
  - `test_runner_empty_selection_has_no_archive_effects` — line 232, 12 lines
  - `_bundle_source` — line 246, 6 lines
  - `_reason` — line 254, 2 lines
  - `test_bundle_out_inside_selected_item_fails_identically_in_every_mode` — line 269, 17 lines
  - `test_bundle_out_under_source_outside_items_plans_runs_and_archives_only_items` — line 303, 25 lines
  - `test_whole_tree_out_under_source_keeps_source_message_in_every_mode` — line 333, 13 lines
  - `test_bundle_out_equal_to_source_keeps_source_message_in_every_mode` — line 351, 12 lines
  - `test_invalid_items_win_over_containment_in_every_mode` — line 375, 12 lines
  - `test_bundle_plan_marks_existing_out_under_source_as_replaced_and_rerun_succeeds` — line 390, 16 lines
- `tests/tools/sysup/test_default_config.py`
  - `_plan_names` — line 6, 7 lines
  - `TestDefaultConfigEquivalence.test_darwin_plan_matches_old_sysup_mac` — line 16, 20 lines
  - `TestDefaultConfigEquivalence.test_linux_plan_matches_old_sysup_wsl` — line 37, 5 lines
  - `TestDefaultConfigEquivalence.test_nvim_is_a_cross_platform_mason_capability` — line 43, 10 lines
  - `TestDefaultConfigEquivalence.test_darwin_does_not_include_linux_entries` — line 54, 4 lines
  - `TestDefaultConfigEquivalence.test_linux_does_not_include_darwin_entries` — line 59, 4 lines
  - `TestDefaultConfigEquivalence.test_uv_tool_python_runs_before_unchanged_uv_upgrades` — line 64, 11 lines
  - `TestDefaultConfigEquivalence.test_pip_runs_between_npm_check_and_uv_on_darwin` — line 76, 5 lines
  - `TestDefaultConfigEquivalence.test_default_primes_sudo` — line 82, 4 lines
  - `TestDefaultConfigEquivalence.test_brew_is_a_run_entry_with_early_abort_sequence` — line 87, 8 lines
  - `TestDefaultConfigEquivalence.test_brew_upgrade_leaves_self_updating_casks_alone` — line 96, 9 lines
  - `TestDefaultConfigEquivalence.test_bundled_steps_are_shell_lines` — line 106, 8 lines
  - `TestDefaultConfigEquivalence.test_mise_self_update_never_waits_for_a_prompt` — line 115, 6 lines
  - `TestDefaultConfigEquivalence.test_rustup_updates_before_mise_builds_cargo_tools` — line 122, 7 lines
  - `TestDefaultConfigEquivalence.test_npm_check_is_interactive` — line 130, 4 lines
  - `TestDefaultConfigEquivalence.test_brew_is_interactive_so_its_sudo_prompt_is_visible` — line 135, 7 lines
  - `TestDefaultConfigEquivalence.test_apt_invokes_sudo_in_every_step` — line 143, 8 lines
  - `TestDefaultConfigEquivalence.test_brew_has_sudo_flag_set` — line 152, 4 lines
  - `TestDefaultConfigEquivalence.test_apt_and_snap_do_not_set_sudo_flag` — line 157, 6 lines
  - `TestDefaultExpiryTemplate.test_gh_agent_template_is_disabled_and_has_no_probe` — line 166, 14 lines
- `uv.lock` — skipped (non-python)

## Tautological test shapes (computed, do not re-judge)

Each `[MECH]` line is a test whose shape cannot fail as written. Raise
it; step 6 adds any line the table lacks. `mech-check` is the finder.


Checked 63 test function(s) in 4 test file(s).

## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `5ae5c53e49ad`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.

replay: skipped (runner produced no results (exit 1: mise ERROR Run with --verbose or MISE_VERBOSE=1 for more information))

## Settled decisions — do not re-raise

> These calls were already made in an earlier cycle of this same review, with
> the reasons given. Do not re-raise them. Raise a NEW finding only if you can
> show the settled reason no longer holds.

- [discarded] medium: Item normalization now runs outside the plan’s OSError handler: simulated unreadable item parents returned a failed PlanEntry before, but now raise PermissionError. Preserve error conversion and add coverage. (src/tools/backup/capabilities/tar_archive.py:285) - reason: single-voice Medium; preserve reported error conversion evidence
- [discarded] medium: Replay confirms 32 added whole-tree/source-equality cases pass against pre-change code, violating the supplied fail-first rule. Reuse existing invariant coverage and make new cases exercise changed precedence. (tests/tools/backup/test_plan_validation.py:333) - reason: single-voice; preexisting invariants intentionally pass against the base
- [discarded] low: Required Fixed entry appears under `0.17.0`; `[Unreleased]` is empty, contrary to Phase 1. (CHANGELOG.md:28) - reason: release 0.17.0 moved the Unreleased entry correctly
- [discarded] low: `_walk_tree` remains 70 lines according to the supplied mechanical facts, exceeding R12's 50-line limit. This function is unchanged; splitting it belongs outside this containment fix. (src/tools/backup/capabilities/tar_archive.py:427) - reason: single-voice; unchanged function outside containment scope
- [discarded] low: The supplied full-suite gate has three failures attributed to host author identity and configured roots. These concern unrelated tools and do not establish a backup regression. (N/A) - reason: single-voice; unrelated host-dependent suite failures retained separately

## Context Pack

Pack file: /Users/bob/git/src/github.com/buvis/gems/docs/dev/tmp/engram-pack-00117-c2.md

### Findings precedent

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00046-dot-tui-secret-status-refresh-v1-review-01.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00046-dot-tui-secret-status-refresh-v1-review-02.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00042-bim-serve-confinement-and-auth-v1-review-01.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00042-bim-serve-confinement-and-auth-v1-review-02.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00043-bim-doc-promote-collision-v1-review-01.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00010-split-long-validator-functions-review-01.md
  ### Outcome (2026-11-01)

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  # Review: 00012-autopilot-package-contract-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  | R2 | [1/3] | 🟠 | resource_closure leaves out many runtime script dependencies. `resource_edges` has 202 rows, yet packaged skills call scripts that are neither packaged nor declared external: `consolidate_findings.py` (plugins/autopilot/skills/run-autopilot/references/lane-solo.md:168, plugins/autopilot/skills/review-work-completion/SKILL.md:386), `compute_mech_facts.py` (plugins/autopilot/skills/fast-track/SKILL.md:270), and also `render_prompt.py`/`record_dispatch.py` in fast-track, `detect_tautological_tests.py`, `check_review_file.py`, `await_reviewer_outputs.py`, `fast_track_plan.py`, `card.py`, `fablectl.py` and `parse_review.py`. The test locks the edge count and digest (tests/autopilot/test_package.py:331), so it cannot catch the gap. The unconditional skill gates block runtime harm today, but later PRDs that restore entry points will inherit this incomplete map | tools/autopilot/source-map.json | Phase 1 task 2 | BLAKE |

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  | R17 | [1/3] | ⚪ | The draft 2020-12 `"type":"integer"` accepts `1.0`, so `attempt: 1.0` passes the schema. The oracle's `range(1, highest + 1)` would then likely raise TypeError instead of returning a defect. The wire test covers 1.5 but not 1.0. | tests/autopilot/test_contract_semantics.py:160 | 3 | BOB |

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-02.md
  autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/tmp/blake-output-ap00012-c2.txt.receipt.json

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00007-extract-memory-candidates-from-transcripts-v1-review-2.md
  ## Cycle-1 rework verification

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00017-malformed-memory-half-written-v1-review-2.md
  | [1/4] | 🟡 | FIX: `target.is_file()` can itself raise `OSError` for an inaccessible parent before `_readable_bytes()` runs, and the handler still catches only `WriteError`/`KeyError`; catch that probe failure and add a regression asserting exit 1 with both files untouched. | skills/distil-memory/scripts/write.py:169 | 5 | BOB |

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00020-changelog-skill-presence-check-v1-review-2.md
  `01a077ec-1aa8-7ef1-96ba-8ed4aab0f82a`)

## Test gate

Tests: counts unavailable (suite run this cycle, exit 0, no PASS/FAIL/SKIP/EXIT summary line)
