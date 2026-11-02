---
prd: docs/dev/project-management/prds/wip/00109-backup-bundle-items-and-skip-outcomes-v1.md
review: 2
date: 2026-11-02
head_sha: 483afbf3da82490f904f61a1660d1f1bdfae04b8
codex_thread_id: 01a19b83-71a6-7d10-b6c2-d684f8d219c5
reviewers: alice,blake,bob,eve
agents:
  alice: available
  blake: available
  bob: available
  carl: disabled
  eve: available
dispatch_rows:
  bob: 4df00997
---

# Review: 00109-backup-bundle-items-and-skip-outcomes-v1

Diff range: `68ca103f06a4b9329de019bb01ac0624b3760838..483afbf3da82490f904f61a1660d1f1bdfae04b8`

codex_rung_guard: fired (1 codex-implemented task(s))

Incremental review of the cycle-1 rework (task 2: tests `403588d2`, fix `f2db27ef`, refactor `483afbf3`). The diff starts at `68ca103f`, not at review-1's `head_sha` `7f4b462f`, because the branch carries PRDs 00110-00112 between the two; `68ca103f` is the rework's own base. Staged with `autopilot review-stage` against `state.json`; path-scoped diff; prior findings and the settled ledger supplied to Alice, Bob and Eve. Pack: ok. Bob resumed his cycle-1 codex thread.

Gate: the isolated full suite at `483afbf` (6405 passed) and the Python 3.14.10 backup suite at `483afbf` (790 passed). Eve's manual fail-first replay against `68ca103f`: 26 of 178 touched tests fail, exactly the pinning tests.

Consolidation: script output corrected model-side. Merged Alice's and Eve's `_item_present` redundancy reports, and Alice's and Eve's missing plan-side tests; the script had merged Eve's plan-item test gap into her separate run-path test finding instead. The ledger auto-dismissed Blake's keyword-only `skipped` re-raise.

## Prior findings (cycle 1)

All five verified resolved by Alice, Bob and Eve: R1 unreadable item fails; R2 unreadable source fails in run and plan on 3.13 and 3.14; R4 `items: null` means omitted and non-list items fail with an exact message; R5 `..hidden` is valid; R6 the empty-bundle skip names its source.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | `docs/source/tools/backup.rst` was not updated for the rework. Line 144 still says "paths beginning with `..` are errors", but `..hidden` is now valid and only a leading `..` component is rejected. The docs also don't say that non-list `items` fails, that `items: null` means omitted, or that an unreadable source or item fails rather than skips. | docs/source/tools/backup.rst:144 | 2 | ALICE, EVE |
| R2 | [2/4] | 🟡 | Plan-side rework behavior is untested: `_plan_items` returning `fail` on an `OSError` from an inaccessible item, `plan` with non-list `items`, `plan` with `items=None` giving `run`, and `plan` accepting a `..name` item. The positive `..notes` case was dropped from the plan parametrization without a replacement. | tests/tools/backup/test_plan.py:345 | 2 | ALICE, EVE |
| R3 | [2/4] | 🟡 | Simplification: `_item_present` calls `os.path.lexists` and then `os.lstat` again to separate absence from access errors. A single `try: os.lstat(path)` with `except (FileNotFoundError, NotADirectoryError): return False` and `return True` behaves the same. | src/tools/backup/capabilities/tar_archive.py:339 | 2 | ALICE, EVE |
| R4 | [1/4] | 🟡 | `_plan_items` short-circuits after the first present item, hiding access errors in later items. Thus `["present.txt", "locked/inner.txt"]` plans as `run`, while reversing the items produces `fail`. | src/tools/backup/capabilities/tar_archive.py:300 | 2 | BOB |
| R5 | [1/4] | 🟡 | The Runner-based unreadable-source test cannot detect a regression in TarArchive.run(): Runner.run pre-plans and drops plan-"fail" instances before run() executes. | tests/tools/backup/test_access_errors.py:56 | 2 | EVE |
| R6 | [1/4] | 🟡 | Rework introduced a mixed, version-dependent access-error contract: _run_validated catches OSError only around _select_items while _normalize_items, _source_kind in run() and _walk_tree propagate; caught messages print without the instance label. | src/tools/backup/capabilities/tar_archive.py:189 | 2 | EVE |
| R7 | [1/4] | ⚪ | The two `TestUnreadableSource` tests pass against the pre-change code on Python 3.11-3.13; they only bind the fix on 3.14. | tests/tools/backup/test_access_errors.py:243 | 2 | ALICE |
| R8 | [1/4] | ⚪ | `_select_items` also drops an item when one of its ancestor directories matches an exclude; consistent with whole-tree pruning but beyond the literal spec. | src/tools/backup/capabilities/tar_archive.py:384 | 2 | BLAKE |
| R9 | [1/4] | ⚪ | Unrequested additions: the `items must be a list of relative paths` error, plan `skip` for an all-absent bundle, and the `no selected items to archive in <source>` wording. | src/tools/backup/capabilities/tar_archive.py:296 | 2 | BLAKE |
| R10 | [1/4] | ⚪ | The `.bkpignore` file is skipped as a member even when it is named directly as an item. | src/tools/backup/capabilities/tar_archive.py:399 | 2 | BLAKE |
| R11 | [1/4] | ⚪ | _source_kind returns a stringly-typed tri-state annotated `str`; a `Literal["dir", "file", "missing"]` return type would let mypy catch a typo. | src/tools/backup/capabilities/tar_archive.py:308 | 2 | EVE |

### Auto-dismissed (ledger)

- [BLAKE] ⚪ `skipped` on `StepResult` is keyword-only (`*, skipped`). | File: src/tools/backup/step_result.py:54 — single-voice

## Alice

Three mediums (R1, R2, R3) and one low (R7). R1 rubric line fails; others pass.

## Blake

Four lows (R8, R9, R10, and the ledger-dismissed `skipped` re-raise). B1-B19 all pass.

## Bob

One medium (R4). R1 and R10 consensus lines fail; others pass.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Eve

Two mediums (R5, R6) and four lows (folded into R1, R2, R3 and R11). KNOWN: engine parametrization on paths that never reach the engine; plan ignores excludes by design (PRD 00110).

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Decision gate

Cycle 2 of cap 2. No CRITICAL or HIGH: the cycle converges. R1, R2 and R3 (two finders each) go to the tail sweep. R4 to R11 are single-voice medium or low, discarded into the ledger. R6 (the mixed access-error contract) and R4 (order-dependent plan check) are recorded in the ledger with their evidence, so a later PRD can pick them up.

Verdict: 11 findings

Tests: 6405 passed, 0 failed, 16 skipped (reused from last-verification.json at 483afbf)
