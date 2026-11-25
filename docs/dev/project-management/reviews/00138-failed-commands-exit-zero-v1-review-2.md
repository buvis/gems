---
prd: docs/dev/project-management/prds/wip/00138-failed-commands-exit-zero-v1.md
review: 2
date: 2026-11-14
head_sha: 333fc0846d61dc3d2b8633c38eed34a4ee7e0e93
codex_thread_id: 01a1d74c-61d9-7473-be11-3d73bec40e56
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: adcba360
  carl: 16c63822
---

# Review: 00138-failed-commands-exit-zero-v1 (cycle 2)

Diff range: `e842a6f6c7fbffb2b7860ce0448d71c9e7f3e2ce..333fc0846d61dc3d2b8633c38eed34a4ee7e0e93`

codex_rung_guard: not fired

## Review Summary

Reviewed: 10 completed tasks (5 original + 5 cycle-1 rework)
PRDs checked: 00138-failed-commands-exit-zero-v1.md
Scope: incremental review of the cycle-1 rework commits.

### Agent Status

- Alice: ✅ Available (consensus lens, Claude subagent)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens, codex, resumed thread `01a1d74c-61d9-7473-be11-3d73bec40e56`; D1-D5 emitted)
- Carl: ✅ Available (gemini via copilot backend)

### Cycle notes

- Engram context pack: failed (`engram pack exit 1: not inside a registered repo`). Reviewers ran with the `(no pack available this cycle)` sentinel. Degraded, not invalid.
- Fail-first replay: skipped (no `--replay-cmd` passed; the cycle-1 attempt failed in this sandbox with `No module named pytest` in the replay worktree).
- Tautological-test check ran over 65 test functions in 5 changed test files and emitted zero `[MECH]` lines.
- No cycle-1 verification-check queue existed, so nothing was carried forward.
- `consolidate_findings.py` emitted Alice's and Bob's `dot pull` test-quality finding as two separate single-voice rows (R1 and R4) because their wording differs. They name one defect at one file:line, so the decision gate merged them into R1 with two finders; the row numbering keeps its gap, R4 is retired, and the consolidated count is 10.
- Every cycle-1 🔴/🟠 finding (R2, R3, R5, R6) is verified resolved by the implementation-aware lenses; the blind lens found no spec gap (B1-B19 all pass).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | The `dot pull` plan-error test only passes because of an accident. `test_pull_failure_from_rescue_plan_bypass_exits_nonzero` never configures `plan()`, so `plan.error` is a truthy MagicMock and the command result carries `error=<MagicMock>`. The design asked for a separate test using `RescuePlan(error="...")`. That test should assert the real error text reaches the output and that `execute` is never called. No such test exists anywhere under `tests/tools/dot`. Add it, and drop the "bypass" comment that relies on mock truthiness. Bob raised the same defect independently: the plan-error test accepts any non-zero exit and the execute-failure test never asserts execution, so configure `RescuePlan(error="planning failed")`, assert the reported error, and assert `execute` is called only in the execute-failure case. | tests/tools/dot/test_dot_commands.py:89 | 9 | ALICE, BOB |
| R2 | [1/4] | 🟡 | The `dot setup` conversion has no exit-code test. `src/tools/dot/cli.py:84` gained `exit_on_failure=True`, but `TestDotSetupCli` has no failing-result case (it only covers URL resolution and the panic path). This is the one converted dot command without a failing-result test. | tests/tools/dot/test_dot_commands.py:244 | 7 | ALICE |
| R3 | [1/4] | 🟡 | `muc tidy` still exits 0 on partial failure. The PRD's source note calls it "the same class". `CommandTidy` hard-codes `success=True` and only emits warnings, so `exit_on_failure` on the aggregate call never fires. The CHANGELOG records this as a deliberate exit-0 case ("Warnings keep exit status 0"), which meets the "list any deliberate exit-0 cases" task. It does not fully close the agoge re-observation. The call is arguable, and the PRD success metric ("after printing a ✘ failure from report_result") is met because no ✘ is printed in that path. | src/tools/muc/commands/tidy/tidy.py:23 | general | BLAKE |
| R5 | [1/4] | ⚪ | The new dot and postup tests are mostly failure-only. Task 3's verify step asks for an exit-0 success case as well. `postup tui` and `postup serve` (tests/tools/postup/adapters/test_cli_exit_codes.py:63 and :77) and the new dot failure tests (tests/tools/dot/test_dot_commands.py:192-237) have no success counterpart. A regression that made these commands always exit non-zero would not be caught. | tests/tools/postup/adapters/test_cli_exit_codes.py:63 | 6 | ALICE |
| R6 | [1/4] | ⚪ | Survey is complete. Every `report_result` call under `src/tools/` passes `exit_on_failure=True`. That covers dot, postup (bare, collect, enrich, brief, tui, serve), puc, bim (note_read, note_write, doc_rules, doc_cli audit), morph, muc, vuc, fren, netscan, zseq and klyreon. The only calls without it are the intermediate per-step calls in `muc tidy`, which cannot fail because the steps never return `success=False`. | src/tools/muc/cli.py:89 | general | BLAKE |
| R7 | [1/4] | ⚪ | Dead branches remain in klyreon `validate` and `export_claims`. In the non-JSON branch the new `exit_on_failure=True` makes the trailing `if not result.success: ctx.exit(1)` unreachable. That code is still live for the `--json` branch, so this is not a bug. The PRD says nothing about it. | src/tools/klyreon/cli.py:158 | general | BLAKE |
| R8 | [1/4] | ⚪ | The `dot status` secret-hiding decision is documented in `dot.rst`: secrets are still hidden on every run, by design, and the exit-code change is noted. `dot status` still performs a write from a read-looking command. That meets the "decide and document" requirement, and I found no code change to the hiding behaviour. | docs/source/tools/dot.rst:129 | general | BLAKE |
| R9 | [1/4] | ⚪ | The CHANGELOG entry is present, names the exit-status change, warns that scripts relying on exit 0 will now see non-zero, and lists the exit-0 exceptions: `muc tidy` and the `bim doc` subcommands (`ingest` and `promote` non-zero only with `--strict`, `triage --approve` always 0). I did not verify it sits under a `### Fixed` heading, only that it is in the Unreleased section. | CHANGELOG.md:52 | general | BLAKE |
| R10 | [1/4] | ⚪ | Tests exist per tool for exit-code behaviour: `test_status_exit_code.py` (dot), `test_cli_brief_exit_code.py` and `test_cli_exit_codes.py` (postup), and `test_cli_exit_code.py` for muc, vuc, morph, puc, fren, netscan, zseq and klyreon, plus bim variants. They cover non-zero on failure and zero on success, including a falsy error message. The cycle gate reports 7695 passed, 0 failed. I did not run the suite. | tests/tools/dot/test_status_exit_code.py:11 | general | BLAKE |
| R11 | [1/4] | ⚪ | No scope creep found. The diff to `src/` is `exit_on_failure` call sites plus removal of the now-redundant `ctx.exit(1)` and `@click.pass_context` lines. No new dependencies and no new CLI flags. | N/A | general | BLAKE |

### Auto-dismissed (ledger)

- [BLAKE] ⚪ No defect found in the core requirement. `report_result` now has an opt-in `exit_on_failure` flag that calls `sys.exit(1)` after the failure output (and after a custom `on_failure` handler). `dot status` and `postup brief` both pass it, so both exit non-zero. | File: src/lib/buvis/pybase/adapters/console/console.py:271 — not a defect; this row records verified positives

## Alice

Consensus lens, implementation-aware. Verified every cycle-1 finding resolved: the dead `ctx.exit(1)` sites are gone (R1), `postup brief` and every dot/postup `report_result` caller now pass `exit_on_failure=True` (R2, R3), the CHANGELOG bullet is narrowed and names the deliberate exit-0 exceptions (R4, R5, R17), the `dot pull` rescue-plan error routes through `report_result` (R6), and `dot.rst` no longer cites the PRD or uses an em dash (R16). Raised three new test-quality gaps in the rework.

Alice did not run the suite; she used this cycle's gate result.

R1: fail
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

Blind lens, PRD-only. Found the code himself and judged spec compliance. Every rubric rule passes: the `exit_on_failure` flag exists with the right semantics, the survey of `report_result` callers is complete across every tool, the CHANGELOG lists the deliberate exit-0 cases, the `dot status` secret-hiding decision is documented, per-tool CliRunner tests exist, and there is no scope creep. He notes `muc tidy` still exits 0 on partial failure and calls the deliberate-exception decision arguable but met.

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

### FIX / VERIFY / KNOWN (doubt buckets, Bob)

FIX:
- F1 — tests/tools/dot/test_dot_commands.py:89 — Use explicit plan fixtures, assert each error appears, and verify whether `execute` ran.

VERIFY:
- (none)

KNOWN:
- (none)

## Bob

Doubt lens (codex, static-only sandbox) plus de-slop, resumed on his cycle-1 thread. He raised one finding: the two `dot pull` failure tests do not pin the paths they claim to, naming the same unconfigured-MagicMock defect Alice found independently.

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
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via copilot backend. No frontend surface in this diff, so he reviewed as a generalist. He ran the dot, postup, bim and klyreon CLI test subsets, mypy on the changed source files and a sphinx docs build, and reported no issues.

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

Verdict: 10 findings
Tests: 7695 passed, 0 failed, 16 skipped (suite run this cycle)
