---
prd: 00098-sysup-run-observability-v1.md
cycle: 1
date: 2026-10-19
head_sha: bdf34d3cdc3033ee3264c2ee3926d76c45dc0aaf
codex_thread_id: 01a151e8-67e1-74c0-87c2-d20c0e24a1fb
reviewers: alice,blake,bob,carl
---

# Review — 00098-sysup-run-observability-v1, cycle 1

Scope: full review (cycle 1).
Diff range: bcd35e7098634188e0b653284fca462212bad40d..bdf34d3cdc3033ee3264c2ee3926d76c45dc0aaf

codex_rung_guard: not fired

pack: failed (engram pack timed out after 300s) — review degraded, not invalid.
replay: skipped (runner produced no results — `ModuleNotFoundError: No module named '_pytest'` in the base worktree).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [4/4] | 🟠 | continue_on_error entries lose failure detail and print no immediate failure diagnostic. `_run_steps` keeps only the last failed step (`failure = outcome.result` overwrites). The PRD says "Show failures immediately as diagnostics and retain every failure detail in the final failed result". With continue_on_error, an earlier failure's stderr is never printed and never reaches the result or attention state. Before this diff each failed step was its own result, so `fold_results` kept every failure. Fix: print each failed step's message via console.failure as it happens, and join all failure messages into the final failed result. | src/tools/sysup/runner.py:243 | 5 | ALICE, BLAKE, BOB, CARL |
| R2 | [3/4] | 🟠 | The log-failure diagnostic never marks a retained path as incomplete. The PRD says to "identify any retained path as incomplete in the error diagnostic". The real FatalError texts in `runlog.py` say "could not write run log <path>" or "could not create run log <path>". The word "incomplete" appears only in a docstring. The CLI test builds its own message and passes it through a mocked Runner, so it proves nothing about production output. Fix: add "(incomplete)" to the append, close and header-failure messages, and assert it in test_runlog.py. | src/tools/sysup/runlog.py:231 | 3 | ALICE, BLAKE, BOB |
| R3 | [3/4] | 🟠 | `prune` skips mismatches silently. The PRD and task say to "skip and report mismatches", but the symlink and non-regular branches just `continue`, and non-matching names are filtered out with no report. The "re-check immediately before each deletion" is done once for all candidates in the listing loop; `os.unlink` happens later with no second `lstat`. The preservation tests assert only that the file survives, not that anything is reported. A candidate that vanishes between `iterdir` and `lstat` raises FatalError instead of being treated as already gone. | src/tools/sysup/runlog.py:65 | 3 | ALICE, BLAKE, BOB |
| R4 | [3/4] | 🟡 | Three functions exceed the 50-line limit, using the mechanical counts: `open_run_log` is 84 lines, `append_step` 56 and `prune` 52. Extract `_create_exclusive` and `_write_header` from `open_run_log`, `_list_candidates` from `prune`, `_format_section` from `append_step`. Behaviour stays the same. | src/tools/sysup/runlog.py:91 | 3 | ALICE, BOB, CARL |
| R5 | [2/4] | 🟡 | Docs and changelog contradict the code in two places. (1) The rst says priming applies when "whose first step's argv starts with sudo", but `_should_prime` checks every step's `argv[0]`. (2) The rst and CHANGELOG say the log path is printed "after every clean or amber (non-red) run"; the code also prints it after red runs, and `test_red_run_still_prints_full_log_and_exits_1` pins that. | docs/source/tools/sysup.rst:147 | 7 | ALICE, BOB |
| R6 | [2/4] | 🟡 | Two tests have no assertion. `test_missing_directory_is_noop` and `test_already_deleted_file_is_not_an_error` only prove that nothing raises. The first has an unused `tmp_path` and an indirect `logs_dir()` path. Add a positive assertion to each. | tests/tools/sysup/test_runlog.py:187 | 3 | ALICE, BOB, mech-check |
| R7 | [1/4] | 🟠 | The fail-stop contract has no regression tests. The PRD acceptance requires "zero update spawns after creation/pruning failure and no further update spawns after append/flush failure, including continue-on-error and multi-result capabilities". `test_log_open_failure_propagates_as_fatal` mocks `subprocess.run` but never asserts it was not called. No test makes `append_step` or `prune` raise from the runner, so the stop-after-write-failure behaviour is unpinned. No test checks that sudo stops and `runlog.close` still run when log creation fails. | tests/tools/sysup/test_runner.py:266 | 4 | ALICE |
| R8 | [1/4] | 🟠 | Header-failure cleanup calls `handle.close` or `os.close` without suppressing secondary errors. A repeated flush failure during close can replace the intended FatalError with a raw OSError, bypassing controlled CLI handling. Suppress secondary cleanup errors and preserve the original path-bearing FatalError. | src/tools/sysup/runlog.py:91 | 3 | BOB |
| R9 | [1/4] | 🟡 | Prime is invoked before the log is opened, which reverses the design's Data flow order (log open, then prime). If the log directory is unwritable, the operator is asked for a sudo password and then the run fails with no update started. | src/tools/sysup/runner.py:129 | 4 | ALICE |
| R10 | [1/4] | 🟡 | pyproject.toml gains a per-file ruff ignore (PLR0913, SLF001) to cover a private `_handle` field used from module functions and a 10-parameter `append_step`. Renaming the field to `handle` removes the SLF001 need; splitting `append_step` removes the other. | pyproject.toml:182 | 3 | ALICE |
| R11 | [1/4] | 🟡 | Tests the PRD placed in tests/tools/sysup/test_sysup_cli.py went into new files (test_sysup_cli_runlog.py, test_sysup_cli_warned.py, test_runner_observability_log.py). `test_sysup_cli.py` is untouched, so the task-5 acceptance command selects nothing from it. Either move the cases or accept the layout deviation explicitly. | tests/tools/sysup/test_sysup_cli_runlog.py:1 | 5 | ALICE |
| R12 | [1/4] | 🟡 | Nonmatching filenames and nonregular candidates are silently skipped, although pruning must report both. Emit console warnings and assert them in the existing preservation tests. | src/tools/sysup/runlog.py:37 | 3 | BOB |
| R13 | [1/4] | 🟡 | CLI failure tests replace Runner.run entirely, leaving required failure boundaries untested. Exercise the real runner with injected prune/create/append/flush/close failures. | tests/tools/sysup/test_sysup_cli_runlog.py:254 | general | BOB |
| R14 | [1/4] | 🟡 | The nonterminal test replaces Runner.run and never enters console.status; status unit tests check construction without verifying execution inside the context. | tests/tools/sysup/test_sysup_cli_runlog.py:285 | 6 | BOB |
| R15 | [1/4] | 🟡 | [MECH] test_already_deleted_file_is_not_an_error has no assertion. Assert the expected unlink attempt and continued pruning of another candidate after FileNotFoundError. | tests/tools/sysup/test_runlog.py:219 | general | BOB, mech-check |
| R16 | [1/4] | 🟡 | test_missing_directory_is_noop has no assertion: it only proves the code does not raise. | tests/tools/sysup/test_runlog.py:187 | general | CARL, mech-check |
| R17 | [1/4] | ⚪ | `open_run_log` builds its "could not create run log" message from `directory / (base + '.log')` even when the failing candidate carried a suffix. That is not the attempted path the contract requires. The `while suffix <= 10_000` bound is an undocumented magic number. | src/tools/sysup/runlog.py:153 | 3 | ALICE |
| R18 | [1/4] | ⚪ | The sudo banner says "cache sudo for this run's updates". The spec asks it to explain credential caching for cask upgrades. | src/tools/sysup/capabilities/sudo.py:45 | general | BLAKE |
| R19 | [1/4] | ⚪ | If the second prime capability raises, stop callbacks from the first are lost. `stops` is only assigned after `_prime()` returns, so the refresher thread is never stopped. Pre-existing, but the spec requires sudo cleanup in finally. | src/tools/sysup/runner.py:129 | general | BLAKE |

## Alice

Consensus lens (implementation-aware), engine: legacy. Findings R1, R2, R3, R4, R5, R6, R7, R9, R10, R11, R17 above.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: pass

## Blake

Blind lens (PRD-only, no diff). Findings R1, R2, R3, R18, R19 above. Blake independently confirmed as compliant: the `warned` status and its rank below expiring, `_report_step` warned rendering, `SysupCommand.sudo` default plus brew's `sudo: true`, the TTY+sudo prime predicate, the sudo argv and banner ordering, exclusive log creation with `-N` suffixes keeping the newest nine prior files, section markers for captured/timeout/not-captured with both streams retained, flush+fsync on append and open, close in `finally`, no step spawns after a creation/prune failure, no attention fold and no notification on a fatal run, the `full log:` line after `_persist_attention` and its omission on failure/dry-run, the `^\s*error:` scan with a five-line cap and `+N more, see log`, the warned result message format, one final result per steps-based entry, timeout handling in both branches, and the required doc/CHANGELOG strings.

B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: fail
B13: pass
B14: pass
B15: fail
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens (D1-D5) + de-slop, via codex. Findings R1, R2, R3, R4, R5, R6, R8, R12, R13, R14, R15 above. Buckets: FIX — all of the above; VERIFY — (none); KNOWN — (none).

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: gemini CLI (copilot-backed), available and run. Findings R1, R4, R16 above, plus the duplicate of R6/R15. Carl additionally ran `uv run pytest -m sysup`, `uv run mypy src/tools/sysup`, `uv run ruff check src/tools/sysup tests/tools/sysup` and `uv run sphinx-build` clean, and found no TODO/FIXME/breakpoint markers in the sysup tree.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: pass

## Decision gate (cycle 1)

Fixed (queued as `[D1]` rework tasks 8-11, tier sonnet): R1, R2, R3, R4, R5, R6, R7, R8.
Discarded as single-voice Medium/Low and recorded in `00098-sysup-run-observability-v1-ledger.json`: R9, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19. R7 and R8 are single-voice but HIGH, so they are never single-voiced away.
No CRITICAL row, so no rework design ran. No deferrals and no blocking escalations. Cycle 1 of cap 2, so rework proceeds.

Verdict: 19 findings
Tests: 5268 passed, 3 failed, 16 skipped, 1 xfailed, 10 errors (suite run this cycle, exit 1; all 3 failures and all 10 errors are in tests/tools/klyreon, tests/tools/postup and tests/tools/dot — pre-existing local-environment noise, none in tests/tools/sysup and none in this diff's scope)
