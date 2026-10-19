---
prd: 00098-sysup-run-observability-v1.md
cycle: 2
date: 2026-10-19
head_sha: 0c45c5e79ebc0222d1f776901d3a80a0177af1f4
codex_thread_id: 01a151e8-67e1-74c0-87c2-d20c0e24a1fb
reviewers: alice,blake,bob,carl
---

# Review — 00098-sysup-run-observability-v1, cycle 2

Scope: incremental review of the cycle-1 rework.
Diff range: bdf34d3cdc3033ee3264c2ee3926d76c45dc0aaf..0c45c5e79ebc0222d1f776901d3a80a0177af1f4

codex_rung_guard: not fired

pack: failed (engram pack timed out after 300s) — review degraded, not invalid.
replay: skipped (no `--replay-cmd` passed; the cycle-1 replay already failed with `ModuleNotFoundError: No module named '_pytest'` in the base worktree).
mechanical test checks: 101 test functions checked in 3 files, zero tautological shapes found.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | `append_step` is still 55 lines (def at line 229 to the end at 283, docstring included, counted the same way as cycle 1's 84/56/52). The `_format_section` extraction only swapped the 12-line if/else body for an 11-line multi-line call, so it did not get under the 50-line limit. Simplest behavior-preserving fix: trim the 24-line docstring (move the section-marker table onto `_format_section`'s docstring), or collapse the call. Cycle 1 R4 is only partly resolved: `open_run_log` (45) and `prune` (45) are now under the limit. | src/tools/sysup/runlog.py:229 | 8 | ALICE, CARL |
| R2 | [2/4] | ⚪ | With `continue_on_error`, each failure is printed via console.failure at src/tools/sysup/runner.py:247. The final joined result is then rendered again by the CLI, so the operator sees each failure twice. The joined message also repeats the entry prefix per failure ("multi failed: first boom; multi failed: second boom"). This matches the PRD ("diagnostics are not additional persisted results"), so it is cosmetic only. | src/tools/sysup/runner.py:256 | 10 | ALICE, BLAKE |
| R3 | [1/4] | 🟡 | Prior R2 remains partly unresolved: when os.fdopen fails, the exclusively created file remains, but its diagnostic lacks "incomplete". Add that label to this branch and assert it alongside the retained path. | src/tools/sysup/runlog.py:205 | 8 | BOB |
| R4 | [1/4] | 🟡 | Prior R7 remains partly unresolved: new failure-stop tests cover argv entries only, and the "flush failure" test merely makes append_step raise FatalError. Add a multi-result capability test proving iteration stops, and inject a real flush/fsync failure after successful header creation to verify propagation and cleanup. | tests/tools/sysup/test_runner.py:324 | 9 | BOB |
| R5 | [1/4] | 🟡 | Prior R4 remains unresolved for append_step: the supplied AST count is still 55 lines. Shorten its duplicated design prose while retaining the formatting, durability and ownership guarantees; further helper extraction is unnecessary. | src/tools/sysup/runlog.py:229 | 8 | BOB |
| R6 | [1/4] | 🟡 | Rework pushes test_runner.py beyond the 800-line limit; the supplied AST places its final test at line 832. Move TestRunnerLogWiring into a focused test module. | tests/tools/sysup/test_runner.py:832 | 9 | BOB |
| R7 | [1/4] | 🟡 | Both new secondary-close-error tests leak real file descriptors: one replaces fdopen with a handle that never owns the descriptor, and the other replaces os.close with an exception. Mock os.open to return a sentinel descriptor in these isolated error-path tests. | tests/tools/sysup/test_runlog.py:105 | 8 | BOB |
| R8 | [1/4] | ⚪ | The `_fdopen` failure branch of `_write_header` leaves a created, empty log file on disk but its FatalError ("could not create run log <path>: ...") lacks "(incomplete)". The header-flush, append and close messages all carry it. The PRD says any retained path must be identified as incomplete. Add " (incomplete)" to that message. | src/tools/sysup/runlog.py:212 | 8 | ALICE |
| R9 | [1/4] | ⚪ | `prune` now emits a console.warning "no longer a disposable run log" when a candidate vanishes before the pre-delete re-check (`_is_disposable_log` returns False on FileNotFoundError). The docstring (src/tools/sysup/runlog.py:97) says such a vanished candidate is "treated as already-pruned, not an error". Either return a tri-state and skip silently on vanish, or reword the docstring. `test_candidate_vanishing_before_restat_is_skipped` (tests/tools/sysup/test_runlog.py:632) does not pin which. | src/tools/sysup/runlog.py:39 | 8 | ALICE |
| R10 | [1/4] | ⚪ | A `FatalError` from `runlog.close()` in the `finally` can mask the original exception. A failed close after a fully complete run also labels the log "(incomplete)", although it was complete and all updates ran. The "(incomplete)" label is accurate for append or flush failures. | src/tools/sysup/runlog.py:317 | 4 | BLAKE |
| R11 | [1/4] | ⚪ | Only log-origin `FatalError`s name the retained log as incomplete. A `FatalError` raised mid-run from a capability or `check_items` while a log is open prints its own message with no mention of the retained path. The spec says to "identify any retained path as incomplete in the error diagnostic". | src/tools/sysup/cli.py:193 | 6 | BLAKE |
| R12 | [1/4] | ⚪ | If `write_state` fails after a completed run, `console.panic` fires and the `full log:` line is never printed (cli.py:198-201). The run completed and the log is complete, so the spec's "for completed runs, print the path" is arguably violated. | src/tools/sysup/cli.py:198 | 6 | BLAKE |
| R13 | [1/4] | ⚪ | Run logs are created with mode 0o644 (runlog.py:188) and hold complete, unredacted stdout and stderr of update commands. The spec does not state a mode. A stricter mode such as 0o600 would be safer for evidence that may contain secrets. There is also a small unlink-after-`lstat` TOCTOU window in prune. | src/tools/sysup/runlog.py:188 | 3 | BLAKE |
| R14 | [1/4] | ⚪ | pyproject.toml adds per-file ruff suppressions (`PLR0913`, `SLF001`) for runlog.py. The spec does not call for these, and they conflict with the repo's warnings policy. | pyproject.toml:179 | 3 | BLAKE |
| R15 | [1/4] | ⚪ | The changelog "Changed" bullet "a run-log write failure now stops the run instead of continuing silently" describes a prior behavior that never existed, because the log is new in this change. | CHANGELOG.md:19 | 8 | BLAKE |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 The sudo banner omits the stated purpose. The spec requires one info line "explaining credential caching for cask upgrades". The implemented text never mentions cask upgrades. | File: src/tools/sysup/capabilities/sudo.py:45 — single-voice
- [BLAKE] 🟡 Prime runs before the log is pruned and created, so a log-creation failure prompts for a sudo password and then aborts. | File: src/tools/sysup/runner.py:129 — single-voice

No 🔴 CRITICAL and no 🟠 HIGH finding this cycle. Every cycle-1 🟠 (R1, R2, R3) and every cycle-1 🟠 single-voice finding (R7, R8) was verified resolved in the code by Alice; the residue is 🟡/⚪ polish.

## Alice

Consensus lens (implementation-aware), engine: legacy. Findings R1, R2, R8, R9 above.

Prior findings verified resolved: cycle-1 R1 (every continue_on_error failure printed and retained — `test_continue_on_error_prints_and_retains_every_failure` fails against the old last-wins code), R2 ("(incomplete)" on header-flush, append and close failures, asserted against real FatalError text), R3 (prune reports mismatches and re-checks before each unlink; three new tests bind to the behavior), R5 (docs and changelog corrected), R6 (both assertion-free tests now assert), R7 (fail-stop regression tests assert zero `subprocess.run` calls after open or prune failure, and that sudo stop plus `runlog.close` still run), R8 (`contextlib.suppress(OSError)` on both cleanup branches, two new tests fail against the old code). Cycle-1 R4 only partly resolved — `open_run_log` (45) and `prune` (45) are under the limit, `append_step` is not.

Regression check: none found. `uv run pytest tests/tools/sysup -q` → 402 passed. `uv run ruff check src/tools/sysup tests/tools/sysup` clean. Settled items were not re-raised.

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
R12: fail
R13: pass

## Blake

Blind lens (PRD-only). Findings R2, R10, R11, R12, R13, R14, R15 above, plus the two ledger-dismissed re-raises.

He verified against the PRD: config and defaults (`sudo: bool = False`, brew `sudo: true`, `extra="forbid"`, TTY-gated priming), the branded non-fatal sudo prime, the `warned` status and its rank, one final result per steps-based entry with case-insensitive `^\s*error:` matching capped at 5 lines, timeout capture in both branches with partial output retained, `finally` cleanup and the dry-run path, and the whole run-log contract (XDG directory, UTC filename, `O_CREAT|O_EXCL` with `-N` suffixes, prune keeping 9, flush+fsync per append, `FatalError` → `console.panic` with exit 1, `full log:` printed only after `_persist_attention`). Docs and changelog carry the required strings.

He ran `uv run pytest -m sysup -q` himself (402 passed, 0 failed) because the staged test-gate line carried no counts.

B1: fail
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

Doubt lens (codex, resumed thread 01a151e8). Findings R3, R4, R5, R6, R7 above.

FIX: the five findings above.
VERIFY: (none)
KNOWN: (none)

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
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

UI / design lens (gemini via copilot backend). One finding, R1 above.

He re-ran the sysup suite, `uv run mypy src/tools/sysup`, `uv run ruff check src/tools/sysup tests/tools/sysup` and a sphinx docs build, and found no further issue beyond the `append_step` size.

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
R12: fail
R13: pass

Verdict: 15 findings
Tests: 5277 passed, 3 failed, 16 skipped, 1 xfailed, 10 errors (suite run this cycle; the gate parser found no PASS/FAIL/SKIP/EXIT line, so counts are read from docs/dev/tmp/gate-00098c2.log — all 3 failures and 10 errors are pre-existing local-environment noise in tests/tools/klyreon, tests/tools/postup and tests/tools/dot, none in sysup)
