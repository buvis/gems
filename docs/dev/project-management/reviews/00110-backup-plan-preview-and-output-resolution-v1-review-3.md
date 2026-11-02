---
prd: docs/dev/project-management/prds/wip/00110-backup-plan-preview-and-output-resolution-v1.md
review: 3
date: 2026-11-02
head_sha: 5d8ab7088b0262d53240b2f8ca3c74171d95d931
reviewers: alice,blake,bob,eve
agents:
  alice: available
  blake: available
  bob: available
  carl: disabled
  eve: available
---

# Review: 00110-backup-plan-preview-and-output-resolution-v1

Diff range: `690229e9..5d8ab7088b0262d53240b2f8ca3c74171d95d931`

codex_rung_guard: fired (5 codex-implemented task(s))

Attended recovery review of the cycle-2 cap repair (handoff `autopilot/reports/202610292344-review-20261102-handoff.md`). Cycle 2 reached cap 2 with HIGH R5 unresolved (`reviews/...-review-2.md`, `autopilot/reports/00110-c2-paused-state.json`). The attended recovery session repaired all seven cycle-2 findings in `5d8ab708`, which the recovery policy allows for a cap regression. This file is cycle 3: the repair is recorded as the cycle-2 rework (`phase-done rework`), the cap stays 2 and is not raised, and cycle 2's history is untouched. At cycle 3 against cap 2 there is no further rework: the cycle either converges or caps out back to hold.

Reviewed tree: detached worktree at `5d8ab708` (`~/git/src/worktrees/gems/review-00110`). Incremental review of `690229e9..5d8ab708`, path-scoped to `src/`, `tests/`, `docs/source/`, `CHANGELOG.md`; prior findings R1-R7 and the settled ledger supplied to Alice, Bob and Eve. Full isolated suite at `5d8ab708`: run this cycle. Python 3.14.10 backup suite at `5d8ab708` (Eve): 758 passed.

Provider diversity: cycles 1-2 were built on OpenAI gpt-6.1-sol (codex) and the cycle-1 rework on Anthropic Sonnet. Alice, Blake and Eve ran as native Anthropic subagents; Bob ran on codex with the inlined prompt.

Carl: disabled. Pack: failed (worktree not a registered repo). Fail-first replay skipped by the tool; Eve and Alice judged the three new tests fail-first by base inspection.

Consolidation: script output corrected model-side. The script kept apart Alice's R2 and Eve's R5, both about runner.py importing the private `_resolve_paths`; merged below with two finders. Ledger auto-dismissed one Blake re-raise (dangling-symlink `replaces`, single-voice settled).

## Prior findings (cycle 2)

All seven verified resolved by Alice, Eve and Bob: R1 expanded `~/out` and `replaces` on missing input; R2 Fixed bullets folded into Added; R3 timestamp test 49 lines; R4 one six-field contract test; R5 `_fail_metadata` wraps `TarArchive.plan` (passes on 3.13 and 3.14); R6 `_failed_plan_entry` reuses the resolver, keeps source, accepts only string `out`; R7 recovery bounded by `suppress(Exception)`.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | ⚪ | One `suppress(Exception)` in `_failed_plan_entry` wraps both the source and the output resolution. If the stamp expansion raises, the source falls back to the raw, unexpanded string instead of the resolved one. | src/tools/backup/runner.py:69 | 8 | ALICE, EVE |
| R2 | [2/4] | ⚪ | `src/tools/backup/runner.py` imports the private `_resolve_paths` from `backup.capabilities.tar_archive`, which couples the generic runner to a private helper of one capability. | src/tools/backup/runner.py:21 | 8 | ALICE, EVE |
| R3 | [1/4] | ⚪ | Every run-time `fail` plan entry is now pre-empted in `Runner.run`, not just duplicate-output ones; the message text is equivalent, so this is a latent behaviour change and not a defect. | src/tools/backup/runner.py:121 | general | BLAKE |
| R4 | [1/4] | ⚪ | `_failed_plan_entry` and its changelog note about metadata errors failing only one instance are not in the spec. | src/tools/backup/runner.py:42 | general | BLAKE |
| R5 | [1/4] | ⚪ | `_set_plan_clock` has a single caller while test_plan_runner.py keeps the same four lines inline twice | tests/tools/backup/test_plan_errors.py:42 | 8 | EVE |
| R6 | [1/4] | ⚪ | CHANGELOG claims "a metadata error fails only its instance", but on 3.14 `Path.is_dir()/exists()` swallow EACCES so a real metadata error yields `skip: source not found` | CHANGELOG.md:10 | 8 | EVE |
| R7 | [1/4] | ⚪ | `_fail_metadata` and four test names/messages still say "metadata" although the seam is now `TarArchive.plan` raising | tests/tools/backup/test_plan_errors.py:30 | 8 | EVE |

### Auto-dismissed (ledger)

- [BLAKE] ⚪ `replaces` uses `Path.exists()`, so a dangling symlink at `out` reports `replaces=false`. | File: src/tools/backup/capabilities/tar_archive.py:126 — single-voice

## Alice

Two lows (R1, R2). No regressions; R1-R13 all pass.

## Blake

Three lows (R3, R4, and the ledger-dismissed `replaces` re-raise). B1-B19 all pass.

## Bob

✅ No issues found. All R lines pass.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Eve

Five lows (R1, R2, R5, R6, R7). KNOWN: the EACCES-on-3.14 source classification, which PRD 00109's cycle-1 rework (`f2db27ef`, `483afbf3`) has since fixed in both `run` and `plan` at HEAD; `_failed_plan_entry` hard-codes tar-archive semantics while TarArchive is the only capability.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Decision gate

No CRITICAL or HIGH: the cycle converges. R1 and R2 (two finders each) go to the tail sweep. R3-R7 are single-voice lows, discarded into the ledger; R6 is also resolved at HEAD by the 00109 rework, where an unreadable source now fails on every Python version.

Verdict: 7 findings

Tests: 6373 passed, 0 failed, 16 skipped (suite run this cycle)
