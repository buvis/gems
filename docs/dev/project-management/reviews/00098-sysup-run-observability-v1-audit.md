# Decision Audit Log: 00098-sysup-run-observability-v1

PRD: `00098-sysup-run-observability-v1.md`
Started: 2026-10-19T03:01:56Z
Completed: 2026-10-19T03:01:56Z
Autonomous: 32  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: sysup run observability design approach

**Choice**: Dedicated runlog.py module with one exclusively-created append-per-step log handle threaded through Runner; _ArgvOutcome internal type carries stdout/stderr/exit_code out of _run_argv for exit-0 scanning and log writes; conditional sudo priming via per-step argv[0] check across all steps in an entry; warned status ranked below expiring in attention _RANK.

**Rationale**: 3 review dispatches (claude, codex, codex-verify), all cardinal-sin/blocker findings resolved. Unresolved non-blocker: concurrent sysup invocations can race log retention/active-file deletion, out of scope.

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: continue_on_error entries lose failure detail and print no immediate failure diagnostic. `_run_steps` keeps only the last failed step (`failure = outcome.result` overwrites). The PRD says "Show failures immediately as diagnostics and retain every failure detail in the final failed result". With continue_on_error, an earlier failure's stderr is never printed and never reaches the result or attention state. Fix: print each failed step's message via console.failure as it happens, and join all failure messages into the final failed result.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: The log-failure diagnostic never marks a retained path as incomplete. The PRD says to "identify any retained path as incomplete in the error diagnostic". The real FatalError texts say "could not write run log <path>" or "could not create run log <path>"; the word "incomplete" appears only in a docstring. Fix: add "(incomplete)" to the append, close and header-failure messages, and assert it in test_runlog.py.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: `prune` skips mismatches silently. The PRD and task say to "skip and report mismatches", but the symlink and non-regular branches just `continue`, and non-matching names are filtered out with no report. The "re-check immediately before each deletion" is done once for all candidates in the listing loop; `os.unlink` happens later with no second `lstat`. A candidate that vanishes between `iterdir` and `lstat` raises FatalError instead of being treated as already gone.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: Three functions exceed the 50-line limit, using the mechanical counts: `open_run_log` is 84 lines, `append_step` 56 and `prune` 52. Extract `_create_exclusive` and `_write_header` from `open_run_log`, `_list_candidates` from `prune`, `_format_section` from `append_step`. Behaviour stays the same.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: Docs and changelog contradict the code in two places. (1) The rst says priming applies when "whose first step's argv starts with sudo", but `_should_prime` checks every step's `argv[0]`. (2) The rst and CHANGELOG say the log path is printed "after every clean or amber (non-red) run"; the code also prints it after red runs, and `test_red_run_still_prints_full_log_and_exits_1` pins that.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: Two tests have no assertion. `test_missing_directory_is_noop` and `test_already_deleted_file_is_not_an_error` only prove that nothing raises. The first has an unused `tmp_path` and an indirect `logs_dir()` path. Add a positive assertion to each.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: The fail-stop contract has no regression tests. The PRD acceptance requires "zero update spawns after creation/pruning failure and no further update spawns after append/flush failure, including continue-on-error and multi-result capabilities". `test_log_open_failure_propagates_as_fatal` mocks `subprocess.run` but never asserts it was not called. No test makes `append_step` or `prune` raise from the runner, so the stop-after-write-failure behaviour is unpinned. No test checks that sudo stops and `runlog.close` still run when log creation fails.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: Header-failure cleanup calls `handle.close` or `os.close` without suppressing secondary errors. A repeated flush failure during close can replace the intended FatalError with a raw OSError, bypassing controlled CLI handling. Suppress secondary cleanup errors and preserve the original path-bearing FatalError.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R1 continue_on_error loses failure detail and prints no immediate diagnostic (runner.py:243)

**Choice**: fix

**Rationale**: cycle 1: 4/4 consensus; PRD requires immediate diagnostics and every failure detail retained; queued as a D1 rework task

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R2 log-failure diagnostic never marks the retained path incomplete (runlog.py:231)

**Choice**: fix

**Rationale**: cycle 1: 3/4 consensus; PRD wording requirement unmet in production messages; queued as a D1 rework task

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R3 prune skips mismatches silently and does not re-check immediately before unlink (runlog.py:65)

**Choice**: fix

**Rationale**: cycle 1: 3/4 consensus; PRD requires skip-and-report plus a per-file re-check; queued as a D1 rework task

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R4 open_run_log 84 lines, append_step 56, prune 52 exceed the 50-line limit (runlog.py:91)

**Choice**: fix

**Rationale**: cycle 1: 3/4 consensus, mechanical extraction with no behaviour change; queued as a D1 rework task

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R5 docs and CHANGELOG contradict the code on sudo priming scope and log-path printing (sysup.rst:147)

**Choice**: fix

**Rationale**: cycle 1: 2/4 consensus, clear mechanical doc fix; queued as a D1 rework task

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R6 two runlog tests have no assertion (test_runlog.py:187)

**Choice**: fix

**Rationale**: cycle 1: 2/4 consensus plus the mechanical tautological-test check; additive test fix; queued as a D1 rework task

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R7 fail-stop contract has no regression tests (test_runner.py:266)

**Choice**: fix

**Rationale**: cycle 1: single-voice but HIGH, which is never single-voiced away; PRD acceptance names the contract explicitly; queued as a D1 rework task

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R8 header-failure cleanup does not suppress secondary close errors (runlog.py:91)

**Choice**: fix

**Rationale**: cycle 1: single-voice but HIGH; a raw OSError would bypass controlled CLI handling; queued as a D1 rework task

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R9 prime runs before the log is opened, reversing the design data-flow order (runner.py:129)

**Choice**: discard

**Rationale**: cycle 1: single-voice medium, discarded and ledgered; no PRD requirement pins the order

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R10 pyproject per-file ruff ignore for PLR0913/SLF001 (pyproject.toml:182)

**Choice**: discard

**Rationale**: cycle 1: single-voice medium, discarded and ledgered

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R11 observability tests landed in new files rather than test_sysup_cli.py (test_sysup_cli_runlog.py:1)

**Choice**: discard

**Rationale**: cycle 1: single-voice medium, discarded and ledgered; a layout deviation, not a behaviour gap

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R12 nonmatching and nonregular prune candidates are skipped without report (runlog.py:37)

**Choice**: discard

**Rationale**: cycle 1: single-voice medium, discarded and ledgered; the reportable-mismatch requirement is carried by R1-class finding R3, which is being fixed

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R13 CLI failure tests replace Runner.run, leaving failure boundaries untested (test_sysup_cli_runlog.py:254)

**Choice**: discard

**Rationale**: cycle 1: single-voice medium, discarded and ledgered; the fail-stop test gap is carried by R7, which is being fixed

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R14 the nonterminal test replaces Runner.run and never enters console.status (test_sysup_cli_runlog.py:285)

**Choice**: discard

**Rationale**: cycle 1: single-voice medium, discarded and ledgered

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R15 test_already_deleted_file_is_not_an_error has no assertion (test_runlog.py:219)

**Choice**: discard

**Rationale**: cycle 1: single-voice duplicate of R6, which is being fixed and covers the same test

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R16 test_missing_directory_is_noop has no assertion (test_runlog.py:187)

**Choice**: discard

**Rationale**: cycle 1: single-voice duplicate of R6, which is being fixed and covers the same test

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R17 create-failure message uses the base path, not the attempted suffixed candidate (runlog.py:153)

**Choice**: discard

**Rationale**: cycle 1: single-voice low, discarded and ledgered

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R18 sudo banner wording does not mention cask credential caching (sudo.py:45)

**Choice**: discard

**Rationale**: cycle 1: single-voice low, discarded and ledgered

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R19 stop callbacks lost when a second prime capability raises (runner.py:129)

**Choice**: discard

**Rationale**: cycle 1: single-voice low, discarded and ledgered; pre-existing behaviour outside this PRD's diff

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R1: append_step is still 55 lines, over the 50-line limit (ALICE, CARL)

**Choice**: swept to a tail-sweep task

**Rationale**: two-voice actionable medium on a converged cycle

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R2: continue_on_error failures are printed twice (console.failure plus the joined final result) (ALICE, BLAKE)

**Choice**: discarded

**Rationale**: cosmetic only; both reviewers read it as PRD-sanctioned, diagnostics are not additional persisted results

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: R3-R15: thirteen single-voice medium/low findings (fdopen incomplete label, fail-stop test depth, append_step duplicate, test_runner.py over 800 lines, fd leaks in two error-path tests, prune vanish-warning wording, close() masking, non-log FatalError path naming, write_state failure path, 0o644 log mode, ruff per-file ignores, changelog wording)

**Choice**: discarded

**Rationale**: single-voice; each recorded in the settled-decisions ledger so a re-raise is auto-dismissed

### [autonomous] 2026-10-19T03:01:56Z

**Decision**: `append_step` is still 55 lines (def at line 229 to the end at 283, docstring included, counted the same way as cycle 1's 84/56/52). The `_format_section` extraction only swapped the 12-line if/else body for an 11-line multi-line call, so it did not get under the 50-line limit. Simplest behavior-preserving fix: trim the 24-line docstring (move the section-marker table onto `_format_section`'s docstring), or collapse the call. Cycle 1 R4 is only partly resolved: `open_run_log` (45) and `prune` (45) are now under the limit.

**Choice**: auto-fixed

**Rationale**: fixed by review-close
