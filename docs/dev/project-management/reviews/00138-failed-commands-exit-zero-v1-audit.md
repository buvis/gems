# Decision Audit Log: 00138-failed-commands-exit-zero-v1

PRD: `00138-failed-commands-exit-zero-v1.md`
Started: 2026-11-14T01:05:29Z
Completed: 2026-11-14T01:05:29Z
Autonomous: 14  |  Deferred: 5  |  Doubts: 0

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: pre-existing redundant ctx.exit(1) guards after report_result

**Choice**: left in place, not removed

**Rationale**: Pat (task 3 review) flagged klyreon/cli.py, bim/note_write_cli.py, bim/note_read_cli.py as now doubly-covered by exit_on_failure=True; out of this PRDs scope

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: R2/R3: postup brief and 16 dot/postup report_result callers still exit 0 on failure, so both PRD success metrics are unmet

**Choice**: fix in cycle-1 rework, preceded by a rework design pass

**Rationale**: the two CRITICALs are the PRD's own named evidence commands and its headline metric; cycle 1 < cap 2, so rework is allowed

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: R10-R13: six mechanical tautological-test-shape findings naming pre-existing tests the diff never touched

**Choice**: settled-deferral, ledgered

**Rationale**: out of this PRD's exit-status scope; fixing untouched tests would widen the diff beyond the request (Surgical Changes)

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: R7, R8, R9, R14-R19: single-voice medium and low findings

**Choice**: discarded as single-voice, ledgered

**Rationale**: the gate's single-voice rule discards medium and low rows raised by one reviewer; the substance of R8, R14, R15, R16, R17 is folded into the R1, R4 and R5 rework tasks rather than dropped

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: Behavior-preserving simplification: every bim and klyreon command that now passes `exit_on_failure=True` still has `if not result.success: ctx.exit(1)` right after the call. That branch is now unreachable, because `report_result` exits first. Delete the dead `ctx.exit(1)` lines, or skip `exit_on_failure` where `ctx.exit(1)` already does the job. Sites: bim/note_read_cli.py:84, :134, :251; bim/note_write_cli.py:82, :304, :355, :390, :437; klyreon/cli.py:128, :149, :225, :244, :268, :284, :296, :306, :328, :340, :350, :367

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: `postup brief`, the PRD's own evidence command, still exits 0 on failure. The conversion went onto the bare `postup` default path in `cli()`, not the `brief` subcommand, whose `console.report_result(result)` call has no `exit_on_failure=True`. The new `TestBarePostupExitCode` tests invoke `cli, []` only, so nothing covers `["brief"]`, and the PRD success metric "`postup brief` exits non-zero" is unmet. Fix: add `exit_on_failure=True` there and a CliRunner test on `["brief"]` with the no-`data.json` scenario

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: The PRD metric "No tool's CLI exits 0 after printing a failure from `report_result`" is unmet for dot and postup. Task 3's file list left both out and Task 2 limited them to one call each, so no task covered the rest. These calls still lack `exit_on_failure`: postup `collect` (:49), `enrich` (:60), `tui` (:87), `serve` (:106); dot `materialize` (:64), `setup` (:82), `add` (:98), `encrypt` (:107), `rm` (:116), `delete` (:125), `pull` (:165), `commit` (:174), `run` (:187), `unstage` (:196), `push` (:204), `localize` (:221, :232). Convert them, or record each as a deliberate exit-0 case

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: The CHANGELOG bullet says "CLI commands now exit non-zero when their command fails". That overclaims while the dot and postup commands above still exit 0. Name the converted tools, or finish the conversion so the sentence is true

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: The phase task "Survey and convert other `report_result` callers; list any deliberate exit-0 cases" is incomplete. Most tools were converted, but dot and postup were left mostly unconverted with no stated reason. No list of deliberate exit-0 cases appears in the CHANGELOG, the docs or the code.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: `dot pull` prints `console.failure(plan.error)` and then returns, so it exits 0 on a rescue-plan error. This bypasses `report_result` entirely, so a conversion of the `report_result` callers alone would not fix it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: Cycle 2 R1 (ALICE) and R4 (BOB) are one defect: the dot pull failure tests at tests/tools/dot/test_dot_commands.py:89 do not pin the paths they claim to (unconfigured plan() MagicMock, no execute assertion). consolidate_findings.py left them as two [1/4] rows because the wording differs.

**Choice**: Treated as one finding with 2/4 consensus, so the single-voice discard rule does not apply; swept as a tail-sweep fix task

**Rationale**: The gate matches on issue text plus file and the consolidator is documented to miss paraphrases; two independent lenses naming the same file:line is consensus, not a single voice

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: Cycle 2 R2, R3 and R5: single-voice medium/low findings (missing dot setup exit-code test, muc tidy aggregate exit 0, failure-only new tests)

**Choice**: Discarded, each appended to the settled-decisions ledger with reason single-voice

**Rationale**: Phase 5 Classification: a single-voice Medium or Low is discarded, never a task; R3 repeats cycle 1's settled R7 call about muc tidy's warnings-only design

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: Cycle 2 R6 to R11: Blake's verified-positive rows (complete report_result survey, live --json branch in klyreon, documented dot status decision, CHANGELOG entry, per-tool exit-code tests, no scope creep)

**Choice**: Discarded, each appended to the settled-decisions ledger

**Rationale**: These rows record verified positives or state explicitly that the observation is not a bug, so there is nothing to fix

### [autonomous] 2026-11-14T01:05:29Z

**Decision**: The `dot pull` plan-error test only passes because of an accident. `test_pull_failure_from_rescue_plan_bypass_exits_nonzero` never configures `plan()`, so `plan.error` is a truthy MagicMock and the command result carries `error=<MagicMock>`. The design asked for a separate test using `RescuePlan(error="...")`. That test should assert the real error text reaches the output and that `execute` is never called. No such test exists anywhere under `tests/tools/dot`. Add it, and drop the "bypass" comment that relies on mock truthiness. Bob raised the same defect independently: the plan-error test accepts any non-zero exit and the execute-failure test never asserts execution, so configure `RescuePlan(error="planning failed")`, assert the reported error, and assert `execute` is called only in the execute-failure case.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [deferred] 2026-11-14T01:05:29Z

**Decision**: `muc tidy` aggregate: `CommandTidy.execute` always returns `success=True`, so the aggregate `exit_on_failure=True` can never fire in production. `test_exits_nonzero_when_aggregate_result_fails` only passes by mocking `CommandTidy` to return a failure it cannot produce.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-11-14T01:05:29Z

**Decision**: `test_valid_dir_passes` and `test_valid_file_passes` have no assertion: they only prove the code does not raise. Pre-existing tests, untouched by this diff.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-11-14T01:05:29Z

**Decision**: `test_limit_not_a_dir` hedges with `or`: either outcome satisfies it. Pre-existing test, untouched by this diff.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-11-14T01:05:29Z

**Decision**: `test_cover_not_a_dir` and `test_tidy_not_a_dir` hedge with `or`: either outcome satisfies them. Pre-existing tests, untouched by this diff.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-11-14T01:05:29Z

**Decision**: `test_multilang_not_a_dir` hedges with `or`: either outcome satisfies it. Pre-existing test, untouched by this diff.

**Choice**: deferred

**Rationale**: deferred by review-close
