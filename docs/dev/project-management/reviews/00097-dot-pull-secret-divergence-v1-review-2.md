---
prd: docs/dev/project-management/prds/backlog/00097-dot-pull-secret-divergence-v1.md
review: 2
date: 2026-10-16
head_sha: db883dba8c5a041163db1483ff7afe09deed458a
codex_thread_id: 01a14690-ed9e-7bf1-b138-22b20a7a7259
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00097-dot-pull-secret-divergence-v1

Diff range: `9cdb8a97a61f94cf7e053294af053c24d46d8734..db883dba8c5a041163db1483ff7afe09deed458a`

codex_rung_guard: not fired

Cycle: 2 (incremental review of rework commit db883dba since cycle 1's head 9cdb8a97). Consensus engine: legacy. Doubt reviewer: codex (no state file, so the codex guard had no attempts record to consult).

Standalone run: no `state.json`, no tasks. The PRD is still in `backlog/` (no `wip/` dir), passed to `review-stage` by path. Settled-decisions ledger and cycle-1 findings were fed to Alice, Bob and Carl (Blake stays blind). No dispatch rows: `review-stage` opens them only under `--state`.

pack: failed (engram pack exit 1: not inside a registered repo; the worktree is not gita-registered). Reviewers ran without the context pack.

Fail-first replay: skipped (the diff touches no test function). Tautological test shapes: none (25 test functions checked).

## Review Summary

Reviewed: 0 tracked tasks (standalone; see above)
PRDs checked: 00097-dot-pull-secret-divergence-v1.md

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available, after one retry (inlined). The resumed codex run could not read the staged files and returned a lack-of-input refusal (all R fail, one ⚪ "remains unreviewed" line with a `- ` prefix). The inlined retry (`bob-prompt-r00097c2-retry.md`, without `--resume-thread`) produced a usable review.
- Carl: ✅ Available (backend copilot, model gemini-3.8-flash)

## Prior findings (cycle 1)

- R1 (negative-guard tests pass at base): discarded in cycle 1; no reviewer showed the reason no longer holds.
- R2 (`pull` 56 lines): resolved. Mech facts: `DotGitService.pull` is 50 lines.
- R3 (`service.py` 804 lines): resolved. `service.py` is 747 lines; `save_divergence_patch` and `_diff_argv` live in `src/tools/dot/divergence.py` (110 lines).

## Consolidated Findings

Produced by `consolidate_findings.py` over all four outputs, with `--ledger ... --ledger-dismiss BLAKE` (nothing auto-dismissed). No carried-forward checks (standalone) and no `[MECH]` lines to absorb.

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟠 | Phase 0 acceptance says every pre-existing test passes unedited, and that `test_pull_divergence.py` is untouched outside `TestSecretHide`. The refactor edited the existing `Harness` monkeypatch targets from `dot.git.service.*` to `dot.divergence.*` | tests/tools/dot/test_pull_divergence.py:61 | 1 | BLAKE |
| R2 | [1/4] | 🟡 | Out-of-spec refactor: `_save_divergence` moved from `DotGitService` into `save_divergence_patch` in `dot/divergence.py`; the PRD names no divergence.py change | src/tools/dot/divergence.py:45 | 1 | BLAKE |
| R3 | [1/4] | ⚪ | The hide step sits inside `_save_and_reset_divergence`, not in `pull` before the call to it; command order is the same | src/tools/dot/git/service.py:204 | 1 | BLAKE |
| R4 | [1/4] | ⚪ | All-clear summary line (hide fail-closed, hint, docs, TestSecretHide (a)-(e), real-git cases ran, mypy clean, test_git_service.py untouched) | N/A | general | BLAKE |

## Dispositions (standalone: reported, not written as tasks)

Checked against the code and git history.

- **R1: accept the deviation (discard), flagged.** Confirmed as stated: lines 61-63 date from 00095 (`1857e376`) and db883dba changed them, so the literal "unedited" wording is not met. What changed is only the three monkeypatch target strings. They follow the code the cycle-1 R3 fix moved, and no assertion or expected command list changed. The criterion's own check (`git diff --stat master -- tests/tools/dot/test_git_service.py`) is empty. The intent, that existing behavior stays pinned by unchanged assertions, holds. The only ways to restore the old strings are to leave `service.py` over 800 lines (R13) or to route `dot.divergence` lookups through `dot.git.service`, which is a test-only seam hack. Implementation-aware reviewers (Alice, Bob, Carl) saw the edit and passed it.
- **R2: discard.** This is the cycle-1 R3 fix (ledger: fixed, "_save_divergence moved to dot.divergence.save_divergence_patch"). It is a behavior-preserving move: same argv, header and error strings, and the 262 dot pull tests are green.
- **R3: discard.** This is the cycle-1 R2 fix (ledger: fixed, "hide step moved to the top of _save_and_reset_divergence, pull's only callee and only inside the upstream branch"). `TestSecretHide` (a)-(c) pin the call order.
- **R4: discard.** It is a pass summary, not a defect.

Net: no open defects. Every row is dismissed with evidence, and the four entries are appended to the ledger.

## Alice

No findings. She verified cycle-1 R2 and R3 resolved and R1 still settled. She ran `uv run pytest tests/tools/dot` (941 passed, 10 skipped, 1 xfailed), the three pull files (46 passed, 0 skipped), mypy and ruff (clean). R1-R13: all pass.

## Blake

Four findings (R1-R4 above). B6 and B15 fail (the unedited-test and scope criteria behind R1/R2); all other B rules pass. He ran `uv run pytest tests/tools/dot` (941 passed, 10 skipped, 1 xfailed) and mypy (clean). All three real-git cases ran.

## Bob

After one retry (inlined). No findings; FIX, VERIFY and KNOWN are empty.

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

Backend copilot, model gemini-3.8-flash. No findings. Ran `pytest -m dot`, the pull test files, mypy, and the `test_git_service.py` diff check (empty). R1-R13: all pass.

Verdict: 4 findings
Tests: 5119 passed, 3 failed, 16 skipped (suite run this cycle; 1 xfailed; the 3 failures are the known env-only tests: 2 klyreon identity, 1 postup collect)
