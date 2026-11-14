---
prd: docs/dev/project-management/prds/wip/00138-failed-commands-exit-zero-v1.md
review: 1
date: 2026-11-14
head_sha: e842a6f6c7fbffb2b7860ce0448d71c9e7f3e2ce
codex_thread_id: 01a1d74c-61d9-7473-be11-3d73bec40e56
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 926253e2
  carl: 766e8317
---

# Review: 00138-failed-commands-exit-zero-v1

Diff range: `4afffe6db744fc2df8fc39102cc82844ce2d0028..e842a6f6c7fbffb2b7860ce0448d71c9e7f3e2ce`

codex_rung_guard: not fired

## Review Summary

Reviewed: 5 completed tasks
PRDs checked: 00138-failed-commands-exit-zero-v1.md

### Agent Status

- Alice: ✅ Available (consensus lens, Claude subagent)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens, codex; D1-D5 emitted)
- Carl: ✅ Available (gemini via copilot backend, model gemini-3.8-flash)

### Cycle notes

- Engram context pack: failed (`engram pack exit 1: not inside a registered repo`). Reviewers ran with the `(no pack available this cycle)` sentinel. Degraded, not invalid.
- Fail-first replay: skipped (`runner produced no results (exit 1: No module named pytest)` in the replay worktree). No changed test was proven to fail against the pre-change code by replay.
- Six `[MECH]` tautological-shape lines were absorbed into the table below; all six name pre-existing tests the diff did not touch. `mech-check` is carried as a finder on those rows.
- The test gate's first run produced no parseable summary line, so `autopilot verify` ran the suite again through a wrapper that emits one. See the `Tests:` line for the exact scope.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | Behavior-preserving simplification: every bim and klyreon command that now passes `exit_on_failure=True` still has `if not result.success: ctx.exit(1)` right after the call. That branch is now unreachable, because `report_result` exits first. Delete the dead `ctx.exit(1)` lines, or skip `exit_on_failure` where `ctx.exit(1)` already does the job. Sites: bim/note_read_cli.py:84, :134, :251; bim/note_write_cli.py:82, :304, :355, :390, :437; klyreon/cli.py:128, :149, :225, :244, :268, :284, :296, :306, :328, :340, :350, :367 | src/tools/klyreon/cli.py:128 | 3 | ALICE, BOB, CARL |
| R2 | [2/4] | 🔴 | `postup brief`, the PRD's own evidence command, still exits 0 on failure. The conversion went onto the bare `postup` default path in `cli()`, not the `brief` subcommand, whose `console.report_result(result)` call has no `exit_on_failure=True`. The new `TestBarePostupExitCode` tests invoke `cli, []` only, so nothing covers `["brief"]`, and the PRD success metric "`postup brief` exits non-zero" is unmet. Fix: add `exit_on_failure=True` there and a CliRunner test on `["brief"]` with the no-`data.json` scenario | src/tools/postup/adapters/cli.py:73 | 2 | ALICE, BLAKE |
| R3 | [2/4] | 🔴 | The PRD metric "No tool's CLI exits 0 after printing a failure from `report_result`" is unmet for dot and postup. Task 3's file list left both out and Task 2 limited them to one call each, so no task covered the rest. These calls still lack `exit_on_failure`: postup `collect` (:49), `enrich` (:60), `tui` (:87), `serve` (:106); dot `materialize` (:64), `setup` (:82), `add` (:98), `encrypt` (:107), `rm` (:116), `delete` (:125), `pull` (:165), `commit` (:174), `run` (:187), `unstage` (:196), `push` (:204), `localize` (:221, :232). Convert them, or record each as a deliberate exit-0 case | src/tools/dot/cli.py:64 | general | ALICE, BLAKE |
| R4 | [2/4] | 🟡 | The CHANGELOG bullet says "CLI commands now exit non-zero when their command fails". That overclaims while the dot and postup commands above still exit 0. Name the converted tools, or finish the conversion so the sentence is true | CHANGELOG.md:52 | 5 | ALICE, BLAKE |
| R5 | [1/4] | 🟠 | The phase task "Survey and convert other `report_result` callers; list any deliberate exit-0 cases" is incomplete. Most tools were converted, but dot and postup were left mostly unconverted with no stated reason. No list of deliberate exit-0 cases appears in the CHANGELOG, the docs or the code. | CHANGELOG.md:52 | 2 | BLAKE |
| R6 | [1/4] | 🟠 | `dot pull` prints `console.failure(plan.error)` and then returns, so it exits 0 on a rescue-plan error. This bypasses `report_result` entirely, so converting the `report_result` callers alone would not fix it. | src/tools/dot/cli.py:141 | 1 | BLAKE |
| R7 | [1/4] | 🟡 | `muc tidy` aggregate: `CommandTidy.execute` always returns `success=True`, so the aggregate `exit_on_failure=True` can never fire in production. `test_exits_nonzero_when_aggregate_result_fails` only passes by mocking `CommandTidy` to return a failure it cannot produce. Either note this as an unreachable guard, or derive aggregate success from the steps | tests/tools/muc/test_cli_exit_code.py:48 | 3 | ALICE |
| R8 | [1/4] | 🟡 | Test coverage misses the spec's per-tool CliRunner requirement for the `postup brief` subcommand and for every unconverted dot and postup command. The postup test only exercises bare `postup`. | tests/tools/postup/adapters/test_cli_brief_exit_code.py:10 | 1 | BLAKE |
| R9 | [1/4] | 🟡 | The tidy continuation test supplies only one failed step and asserts only exit status. Add a subsequent successful step and assert its output plus the aggregate output. | tests/tools/muc/test_cli_exit_code.py:64 | 3 | BOB |
| R10 | [2/4] | 🟡 | `test_valid_dir_passes` and `test_valid_file_passes` have no assertion: they only prove the code does not raise. Pre-existing tests, untouched by this diff. | tests/lib/pybase/adapters/test_console_adapter.py:420 | general | BOB, CARL, mech-check |
| R11 | [2/4] | 🟡 | `test_limit_not_a_dir` hedges with `or`: either outcome satisfies it. Pre-existing test, untouched by this diff. | tests/tools/muc/test_muc_cli_extra.py:52 | general | BOB, CARL, mech-check |
| R12 | [2/4] | 🟡 | `test_cover_not_a_dir` and `test_tidy_not_a_dir` hedge with `or`: either outcome satisfies them. Pre-existing tests, untouched by this diff. | tests/tools/muc/test_muc_commands.py:24 | general | BOB, CARL, mech-check |
| R13 | [2/4] | 🟡 | `test_multilang_not_a_dir` hedges with `or`: either outcome satisfies it. Pre-existing test, untouched by this diff. | tests/tools/vuc/test_vuc_commands.py:21 | general | BOB, CARL, mech-check |
| R14 | [1/4] | 🟡 | Redundant `ctx.exit(1)` after `report_result(..., exit_on_failure=True)`: unreachable dead code; remove the redundant check | src/tools/bim/note_read_cli.py:84 | 3 | CARL |
| R15 | [1/4] | 🟡 | Redundant `ctx.exit(1)` after `report_result(..., exit_on_failure=True)`: unreachable dead code; remove the redundant check | src/tools/bim/note_write_cli.py:82 | 3 | CARL |
| R16 | [1/4] | ⚪ | In `docs/source/tools/dot.rst` the new paragraph says "this PRD found no reason to drop that protection". User-facing docs should not refer to a PRD. It also uses an em dash, which the writing rules ban. Reword it as a plain statement of the decision | docs/source/tools/dot.rst:129 | 4 | ALICE |
| R17 | [1/4] | ⚪ | The completion report did not list the deliberate exit-0 case in `_report_doc_result` (soft-fail unless `strict`, documented in its docstring). It does not go through `report_result`, but the task asked to list other exit-0 cases found in the survey | src/tools/bim/doc_cli.py:315 | 3 | ALICE |
| R18 | [1/4] | ⚪ | Existing functions exceed the rubric limit: `print_side_by_side` has 52 lines and `query` has 79 lines. Neither changed in this diff. | src/lib/buvis/pybase/adapters/console/console.py:209 | general | BOB |
| R19 | [1/4] | ⚪ | Positives, verified. `report_result` gained `exit_on_failure` (default False, `sys.exit(1)`) after the error output. `dot status` and bare `postup` are converted. The remaining tools (puc, bim, morph, vuc, muc, netscan, zseq, fren, klyreon) pass `exit_on_failure=True`. `dot.rst` documents that `dot status` keeps hiding secrets. | src/lib/buvis/pybase/adapters/console/console.py:306 | 1 | BLAKE |

## Alice

Consensus lens, implementation-aware. Raised the unconverted `postup brief` evidence command and the wider dot/postup gap at 🟠, the overclaiming CHANGELOG bullet, the now-unreachable `ctx.exit(1)` branches, the unreachable `muc tidy` aggregate guard, the PRD reference and em dash in `dot.rst`, and the unlisted `_report_doc_result` exit-0 case.

Alice did not run the suite: the staged context carried a failed gate run with no counts, and the fail-first replay was skipped.

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens, PRD-only. Found the code himself and judged spec compliance. Raised both unconverted-caller findings at 🔴, the bypassing `console.failure` path in `dot pull`, the incomplete survey task, the overclaiming CHANGELOG entry, and the missing `brief`-subcommand test coverage. Verified the positives listed in R19.

B1: fail
B2: pass
B3: fail
B4: pass
B5: fail
B6: pass
B7: fail
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

### FIX / VERIFY / KNOWN (doubt buckets, Bob)

FIX:
- F1 — src/tools/klyreon/cli.py:148 — Remove redundant exits after unconditional terminating reports.
- F2 — tests/tools/muc/test_cli_exit_code.py:64 — Assert that a later step and the aggregate are reported after a failed step.

VERIFY:
- (none)

KNOWN:
- K1-K6 — Pre-existing test bodies and assertions are unchanged; validation-test cleanup is outside this PRD.
- K7 — Neither oversized function changed; splitting them would broaden this exit-status fix.

## Bob

Doubt lens (codex, static-only sandbox) plus de-slop. Raised the redundant failure-exit branches, the thin tidy continuation test, the six mechanical tautological-shape lines as KNOWN, and the two pre-existing oversized functions.

R1: fail
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
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via copilot backend, model `gemini-3.8-flash`. No frontend surface in this diff, so he reviewed as a generalist. Independently raised the same six mechanical tautological-shape lines and three of the redundant `ctx.exit(1)` sites.

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
R12: pass
R13: pass

Verdict: 19 findings
Tests: 7679 passed, 0 failed, 16 skipped (suite run this cycle; tests/tools/dot/test_pull_divergence_two_hosts.py ignored, its 10 errors are pre-existing environment-only gpg-signing setup failures in a file this branch does not touch)
