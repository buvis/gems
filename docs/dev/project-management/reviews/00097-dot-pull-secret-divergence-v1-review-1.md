---
prd: docs/dev/project-management/prds/backlog/00097-dot-pull-secret-divergence-v1.md
review: 1
date: 2026-10-16
head_sha: 9cdb8a97a61f94cf7e053294af053c24d46d8734
codex_thread_id: 01a14652-75d5-7b13-a2f4-0584d0a6842e
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00097-dot-pull-secret-divergence-v1

Diff range: `6309d70b1245..9cdb8a97a61f94cf7e053294af053c24d46d8734`

codex_rung_guard: not fired

Cycle: 1 (full review). Consensus engine: legacy. Doubt reviewer: codex (no state file, so the codex guard had no attempts record to consult).

Standalone run: no `state.json`, no tasks (the work landed as one commit, 9cdb8a97, outside autopilot). The PRD is still in `backlog/` (no `wip/` dir exists), so it was passed to `review-stage` by path. The range starts at the 00095 merge (6309d70b), not the master merge-base, because the branch's master merge pulls in unrelated 00093 work. No dispatch rows: `review-stage` opens them only under `--state`.

pack: failed (engram pack exit 1: not inside a registered repo; the worktree is not gita-registered). Reviewers ran without the context pack.

Fail-first replay: 8 touched tests ran, 6 failed against base, 2 passed (absorbed into R1). Tautological test shapes: none (28 test functions checked).

## Review Summary

Reviewed: 0 tracked tasks (standalone; see above)
PRDs checked: 00097-dot-pull-secret-divergence-v1.md

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available, after one retry (inlined). The first codex run could not start `cat` in its sandbox and returned the lack-of-input refusal shape (all R fail, only ⚪ "Cannot statically verify" lines). The retry gave usable findings but prefixed each issue line with `- ` (format warning). The consolidator skips such lines, so they were parsed from a copy with the prefix stripped (`bob-output-r00097c1.normalized.txt`). The issue text is unchanged.
- Carl: ✅ Available (backend copilot, model gemini-3.8-flash)

## Consolidated Findings

Produced by `consolidate_findings.py` over Alice, Blake, the normalized Bob output, and Carl, plus the absorbed mechanical replay row (mech-check appended to R1). The consolidator merged Bob's two separate replay findings (`:451` and `:476`) into R1.

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | `test_no_upstream_skips_hide` passes against the pre-change code, violating the required fail-first criterion (so does `test_failed_secret_reset_gets_no_hint`) | tests/tools/dot/test_pull_divergence.py:451 | general | BOB, CARL, mech-check |
| R2 | [2/4] | 🟡 | `pull` grows to 56 lines, exceeding the 50-line limit | src/tools/dot/git/service.py:150 | general | BOB, CARL |
| R3 | [2/4] | 🟡 | The service exceeds the 800-line file limit: the supplied mechanical facts place its final method through line 804 | src/tools/dot/git/service.py:789 | general | BOB, CARL |

## Dispositions (standalone: reported, not written as tasks)

Checked against the code and the computed mechanical facts.

- **Fix (rework):** R2 is confirmed by the mech facts: `DotGitService.pull` is 56 lines, and the 6-line hide block pushed it past 50. Moving the hide into a small helper (for example `_hide_edited_secrets() -> str | None`) fixes it and keeps the call order and messages. R3 is confirmed: `service.py` is 804 lines. This commit added 13 net lines and pushed it past 800. The R2 helper does not shrink the file, so a real fix moves the divergence save/reset code (`_save_and_reset_divergence` and its helpers) into its own module, as Bob suggests.
- **Likely dismiss:** R1. Both tests are negative guards the PRD asks for word for word: case (c) says the no-upstream sequence must stay the same as 00095, and case (e) says a failed reset gets no hint. They pass against base by design, the same way a behavior-preserving test does. The positive paths are pinned by (a), (b) and (d), which fail against base. Bob's narrower point on (e) is that it never shows a completed secret reset keeping its hint while a later one fails. That gap is real but small: (d) pins the completed-reset hint.
- **Reviewer verdict note:** Alice gave R12 and R13 a pass. The computed mech facts (56 lines, 804 lines) contradict that, so her two verdicts are overridden here. Her other findings are unaffected.

## Alice

No findings. She ran the dot pull tests (262 passed, 0 skipped) and treats the two replay tests as PRD-mandated guards (c) and (e). Verdicts: all pass (R12 and R13 overridden, see Dispositions).

## Blake

No findings; no spec violations. All hide, hint, test, doc and changelog wording checked against the spec. Ran the three dot test files (262 passed, 0 skipped, git-secret and gpg on PATH). Did not run `pytest -m dot` or mypy. B1-B19: all pass.

## Bob

After one retry (inlined). Four findings (R1 x2, R2, R3), all in FIX. VERIFY and KNOWN are empty. Format warning: the issue lines had a `- ` prefix (see Agent Status).

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend copilot, model gemini-3.8-flash. Three findings (R1, R2, R3). Ran the dot tests, the two-host file, `pytest -m dot` and mypy on dot and lib. Verdicts: R2, R12 and R13 fail, all others pass.

Verdict: 3 findings
Tests: 5119 passed, 3 failed, 16 skipped (suite run this cycle; 1 xfailed; the 3 failures are the known env-only tests: 2 klyreon identity, 1 postup collect)
