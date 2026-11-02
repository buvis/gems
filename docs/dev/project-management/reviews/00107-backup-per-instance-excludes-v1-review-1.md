---
prd: docs/dev/project-management/prds/wip/00107-backup-per-instance-excludes-v1.md
review: 1
date: 2026-11-02
head_sha: 5a3ab34deb025e2a4223f9af876ec0256c2de177
reviewers: alice,blake,bob,eve
agents:
  alice: available
  blake: available
  bob: available
  carl: disabled
  eve: available
---

# Review: 00107-backup-per-instance-excludes-v1

Diff range: `4becb45eb3c0949544dfeec5ed3db3424bcbc4d5..5a3ab34deb025e2a4223f9af876ec0256c2de177`

codex_rung_guard: fired (1 codex-implemented task(s))

Attended recovery review (handoff `autopilot/reports/202610292344-review-20261102-handoff.md`). Completion review never ran for this held fast-track PRD. State restored from `autopilot/reports/00107-backup-per-instance-excludes-v1-build-state.json`; work base and task provenance unchanged.

Reviewed tree: detached worktree at the PRD's build end `5a3ab34d` (`~/git/src/worktrees/gems/review-00107`), so the diff covers only this PRD's implementation, not the later 00109-00112 work on the branch. The staged diff was path-scoped to `src/`, `tests/`, `docs/source/`, `CHANGELOG.md` and `README.md`: the unscoped range added 1.9 MB of autopilot session logs. Staged with `autopilot review-stage` in standalone mode (`--tasks-json`, `--prd`), because the worktree tree does not carry the wip PRD.

Provider diversity: the build ran on OpenAI gpt-6.1-sol via codex. Alice, Blake and Eve ran as native Anthropic subagents in this session; Bob ran on codex with the inlined prompt. The headless `autopilot review-once` route was tried first and failed before review: `claude -p` reported "OAuth token revoked".

Carl: disabled. Backup has no UI surface, and the batch report records Carl failing the nested-dispatch guard before any backend ran.

Pack: failed (engram pack: worktree not a registered repo). Prompts carry `(no pack available this cycle)`. Degraded, not invalid.

Fail-first replay: skipped by the tool (its temporary venv lacked pytest). No `[MECH]` tautological-shape lines. Eve and Alice reasoned replay by hand: every new-field test fails at base; the two rejection tests pass at base and pin PRD-required error cases.

Consolidation: script output corrected model-side. The script kept two paraphrase pairs apart: the `--show-excludes` order change (Alice R4 + Eve R2) and the redundant `tuple()` wraps (Alice R5 + Eve R7). Both pairs are merged below with two finders each. All raw reviewer outputs remain in the worktree's `docs/dev/tmp/`.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | `--show-excludes` print order silently changed from sorted to config order; PRD names only the header change, matching is set-based, and no test pins either order (new test uses substring membership) | src/tools/backup/cli.py:95 | 1 | EVE, ALICE |
| R2 | [2/4] | ⚪ | Test slop in new file: in-body `from backup.config import effective_excludes` beside header imports from the same module; `tuple()` wraps on fields that are already tuples; `assert cfg.excludes == tuple(base)` asserts a frozen model's tuple did not mutate and cannot fail | tests/tools/backup/test_instance_excludes.py:104 | 1 | EVE, ALICE |
| R3 | [1/4] | 🟡 | Two new validation tests exercise existing rejection behavior and pass against pre-change code; add successful controls using the new instance fields before testing rejection. | tests/tools/backup/test_instance_excludes.py:63 | 1 | BOB |
| R4 | [1/4] | 🟡 | PRD parked in `prds/hold/` on 3 batch-suite failures outside the diff (klyreon identity x2, postup collect) that project memory records as env noise; needs an isolated re-run before the PRD leaves hold | N/A | 1 | EVE |
| R5 | [1/4] | ⚪ | Docs drift in touched page: `.bkpignore` bullet still says "the global default" after the intro was reworded to "effective instance list"; new "Instance exclusions" section never states instance patterns are the same gitignore-style fnmatch globs as `excludes` | docs/source/tools/backup.rst:126 | 1 | EVE |

## Alice

Two low findings (merged into R1 and R2). No defects in `effective_excludes`, runner, `_show_excludes`, rejection paths, docs or CHANGELOG. R1-R13: all pass.

## Blake

✅ No issues found. Ran `tests/tools/backup/test_instance_excludes.py`: 22 passed. B1-B19: all pass.

## Bob

One medium finding (R3). Consensus rubric: R2 fail (tied to that finding), every other R line pass.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Eve

Four findings (R1, R2, R4, R5). Re-ran `pytest tests/tools/backup` (142 passed), ruff and mypy clean in the worktree. One format retry: her first output had buckets but no issue lines.

VERIFY (not queued: command shape, it needs an unset Git identity and a scratch `BUVIS_CONFIG_DIR`, which one command line cannot carry): re-run the three env-failure tests isolated. Already done: the recovery report records the unchanged 00111 isolation runner passing all three, and this cycle's gate ran the full suite through that runner.

KNOWN: multi-layer semantics of the instance list fields are out of PRD scope; tests inherit the operator's home config layer through the pre-existing loader.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Decision gate

No CRITICAL or HIGH. Single-voice R3, R4 and R5 are discarded (`single-voice`) into the ledger; R4 is also refuted by the recorded isolation-runner pass. R1 and R2 go to the tail sweep.

Verdict: 5 findings

Tests: 5757 passed, 0 failed, 16 skipped (reused from last-verification.json at 5a3ab34)
