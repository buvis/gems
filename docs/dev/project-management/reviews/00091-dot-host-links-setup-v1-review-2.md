---
prd: docs/dev/project-management/prds/done/00091-dot-host-links-setup-v1.md
review: 2
date: 2026-10-15
head_sha: ceac91d3e8bba592ce59968dd1c35366071095d8
codex_thread_id: 01a13fa1-14c4-73d0-9c95-405df518e9ef
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
  eve: disabled
---

# Review: 00091-dot-host-links-setup-v1

Diff range: `bbabc93934660c4c708a502f71f51c87bc962835..ceac91d3e8bba592ce59968dd1c35366071095d8`

codex_rung_guard: not fired

Run notes (standalone, no `state.json`):

- Incremental review of the cycle-1 rework (2c1cfbc0). The PRD sits in `prds/done/` and there is no `prds/wip/`. As in cycle 1, this review targets the done PRD. There is no task store, so there is no task context.
- Consensus engine: legacy. Doubt reviewer: codex (Bob). Eve not active.
- pack: failed (engram pack exit 1: worktree not a registered gita repo). Prompts carried `(no pack available this cycle)`.
- Mechanical checks: no `[MECH]` lines. The fail-first replay was skipped (no `--replay-cmd`; the base worktree has no synced venv). Cycle 1 already recorded both regression tests failing before the fix.
- Staging gate: `review-stage` could not parse the suite's counts (exit 1, the 3 known env failures). I reran the suite by hand. See `Tests:`.
- Bob's first run resumed his cycle-1 codex thread. His sandbox could not read the inputs: every R rule came back fail as "unverified", and the lines carried a `- ` prefix. He then got his one retry with the inlined prompt (`bob-prompt-c2-20261015-retry.md`), and the retry produced a clean, compliant review.
- Dispatch ledger: standalone run, so no `record_dispatch.py` rows were opened.
- Consolidation: script.

## Consolidated findings

| Ref | Consensus | Severity | Issue | File | Task | Found By | Disposition |
|-----|-----------|----------|-------|------|------|----------|-------------|
| R1 | [1/4] | ⚪ | Step 6 runs `cfg checkout --no-overwrite-ignore` where the PRD names plain `cfg checkout` | src/tools/dot/commands/setup/setup.py:46 | Phase 1 CommandSetup | BLAKE | **Accepted as is.** This is the cycle-1 R7 fix, a deliberate hardening. The CHANGELOG and review 1 record it. `git checkout -h` lists `--[no-]overwrite-ignore`, and the real-git test covers it |
| R2 | [1/4] | ⚪ | A step-4 `status.showUntrackedFiles` failure becomes a warning, which the PRD leaves unspecified | src/tools/dot/commands/setup/setup.py:39 | Phase 1 CommandSetup | BLAKE | **Accepted as is.** It repeats cycle-1 R2, which was already accepted |
| R3 | [1/4] | ⚪ | The `.buvis` guard uses `Path.exists()`, so a dangling symlink at that path passes and the clone runs onto it | src/tools/dot/commands/setup/setup.py:28 | Phase 1 CommandSetup | BLAKE | **Accepted as is.** I checked this with real git: `git clone --bare -- <src> <dangling-link>` exits 0 and creates the repo at the link target. The target did not exist, so nothing is overwritten. That is the same outcome as a fresh path |
| R4 | [1/4] | ⚪ | `check_hooks` checks only `pre-commit`, not post-checkout, post-merge or post-rewrite | src/tools/dot/git/service.py:295 | Phase 0 | BLAKE | **Accepted as is.** It matches the PRD (same family as cycle-1 R5). Widening the check is out of scope |

Prior findings: Alice, Bob and Carl confirmed that cycle-1 R1 (clone `--`) and R7 (`--no-overwrite-ignore`) are fixed, with regression tests. No reviewer raised a regression in the rework. No rework is needed this cycle.

## Alice

✅ No issues found. She confirmed that R1 and R7 are fixed and that every test assertion on the old `cfg checkout` string was updated. `uv run pytest tests/tools/dot/test_setup.py tests/tools/dot/test_setup_real_git.py`: 20 passed.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Four ⚪ findings (R1-R4 above), all minor. He traced every other spec requirement to code. `uv run pytest -m dot`: 863 passed, 10 skipped, 1 xfailed. `uv run mypy src/tools/dot`: clean.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

After one retry (inlined). ✅ No issues found. FIX, VERIFY and KNOWN are all empty, so no verification-check queue was written (standalone run in any case).

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: copilot, model gemini-3.8-flash. ✅ No issues found.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

Verdict: 4 findings

Tests: 4879 passed, 3 failed, 16 skipped (suite run this cycle; 1 xfailed; the 3 failures are known env noise: 2 klyreon git-identity tests, 1 postup collect test calling real gh)
