---
prd: docs/dev/project-management/prds/wip/00094-updater-installer-index-parity-v1.md
review: 1
date: 2026-10-15
head_sha: 03c0eac8cc8e529dfd0e5fb340d41cf834d5aa4e
codex_thread_id: 01a13fae-5048-7662-8025-09b1db289cc4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00094-updater-installer-index-parity-v1

Diff range: `15d872fc6ca1fbb3d3a5a01f4418b686134b9d97..03c0eac8cc8e529dfd0e5fb340d41cf834d5aa4e`

codex_rung_guard: not fired

Cycle: 1 (full review). Consensus engine: legacy. Doubt reviewer: codex (no state file, so the codex guard had no attempts record to consult).

Standalone run: no `state.json`, no tasks (the work landed as one commit, cc59e4f2, outside autopilot). The PRD was in `backlog/`; it was moved to `wip/` (03c0eac8) so the review had its target. No dispatch rows: `review-stage` opens them only under `--state`.

pack: failed (engram pack exit 1: not inside a registered repo; the worktree is not gita-registered). Reviewers ran without the context pack.

Fail-first replay: `review-stage` skipped it (relative `--replay-cmd` did not resolve from the replay worktree); re-run by hand with an absolute interpreter path: 24 touched tests ran, 19 failed against base, 5 passed; 3 test files could not be collected at base. Tautological test shapes: one `[MECH]` line (absorbed into R2).

## Review Summary

Reviewed: 0 tracked tasks (standalone; see above)
PRDs checked: 00094-updater-installer-index-parity-v1.md

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available, after one retry (inlined). The first codex run could not start `cat` in its sandbox and returned an all-fail, uninspected review with `- `-prefixed issue lines; the retry inlined context and diff and asked for column-0 `[BOB]` lines.
- Carl: ✅ Available (backend copilot, model gemini-3.8-flash)

## Consolidated Findings

Produced by `consolidate_findings.py`, plus the absorbed mechanical rows (R18, R19). Known consolidator artifacts, noted rather than hand-edited: R3 merges two different defects (Alice's double `mise where` call and Blake's argv0-fallback no-op risk) after suffix stripping; R9 duplicates R2, and R8/R10 duplicate R1, so the true consensus is R1 [3/4] and R2 [3/4] (ALICE, BOB, CARL, mech-check).

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | force_update is now 57 lines (was 44), over the 50-line limit. run_update (70 lines) and run_update_interactive (59 lines) also grew past it with the verification blocks. Extract the PyPI-lag report from force_update into a helper such as `_report_installer_lag(current, latest)`, and the verify-and-record-no-op block from run_update into a helper | src/lib/buvis/pybase/updater/__init__.py:82 | general | ALICE, BOB, CARL |
| R2 | [2/4] | 🟡 | Touched test `TestPypiUnreachable.test_returns_one_and_prints` has an `or`-hedged assert (mech-check flagged it). Any one of "pypi", "reach" or "unreachable" passes, and the new message "Could not reach the installer's index or PyPI to check for updates." matches several. This test was edited in this diff, so assert the exact new message instead | tests/lib/pybase/updater/test_force_update.py:90 | general | ALICE, BOB, mech-check |
| R3 | [2/4] | ⚪ | On `mise-pipx`, `_resolve_reexec_argv` runs `mise where` twice per successful upgrade, once in `read_installed_version` and once in `_reexec_or_exit`. This is a minor redundant subprocess call, cheap to cache or pass through | src/lib/buvis/pybase/updater/executor.py:316 | general | ALICE, BLAKE |
| R4 | [1/4] | 🟡 | `read_installed_version` has no direct tests for its no-match, invalid-version (`Version()` raises) or non-zero-exit branches. The existing `run_update_interactive` tests mock `subprocess.run` with a bare MagicMock, so `_VERSION_PATTERN.search(MagicMock)` raises TypeError. The broad `except Exception` swallows it, so those tests pass by accident, not through a real parse path. Add parametrized tests (garbage stdout, bad version string, timeout) and give the older interactive mocks a proper `stdout` | src/lib/buvis/pybase/updater/executor.py:329 | general | ALICE |
| R5 | [1/4] | 🟡 | `__init__.py` imports the private `_newer_or_none` from checker, and `index.py` imports the private `_query_pypi` from checker. These private cross-module imports are a style drift. Either make the helper public and export it in `__all__` (for example `newer_or_none`), or compare with `Version` inline as before | src/lib/buvis/pybase/updater/__init__.py:12 | general | ALICE |
| R6 | [1/4] | 🟡 | Interactive updates report success when verification fails: `read_installed_version()` returning `None` reaches “Upgraded.” and exit 0. Return a verification failure instead, and test unavailable/malformed version output; preserve the passive restart fallback. | src/lib/buvis/pybase/updater/executor.py:192 | general | BOB |
| R7 | [1/4] | 🟡 | Installer-cache validation accepts invalid version strings such as `""` or `"garbage"` as fresh records, contrary to the malformed-record cache-miss requirement. Validate with `Version` and add invalid-string cases. | src/lib/buvis/pybase/updater/state.py:105 | general | BOB |
| R8 | [1/4] | 🟡 | `run_update` and `run_update_interactive` are 70 and 59 lines respectively. Extract their post-install verification/reporting phases into focused helpers, preserving the distinct passive and interactive policies. | src/lib/buvis/pybase/updater/executor.py:70 | general | BOB |
| R9 | [1/4] | 🟡 | test_returns_one_and_prints hedges with or: either outcome satisfies it | tests/lib/pybase/updater/test_force_update.py:90 | general | CARL |
| R10 | [1/4] | 🟡 | Function run_update is 70 lines (exceeds 50-line limit); extract post-upgrade verification to a helper | src/lib/buvis/pybase/updater/executor.py:70 | general | CARL |
| R11 | [1/4] | ⚪ | `read_installed_version` ignores the child's `returncode`. A non-zero `--version` that still prints "version X" is accepted as verified. Check `result.returncode == 0` before parsing | src/lib/buvis/pybase/updater/executor.py:324 | general | ALICE |
| R12 | [1/4] | ⚪ | `_is_backed_off` treats a future `ts` (clock skew or a hand-edited file) as inside the window, because the delta is negative and so less than 24h. The back-off then holds until the clock catches up. Bound it with `0 <= delta < UPGRADE_BACKOFF` | src/lib/buvis/pybase/updater/__init__.py:121 | general | ALICE |
| R13 | [1/4] | ⚪ | `executor.py:134` adds an unspecified `warning` log line when verification is unavailable. The spec says only "behaves as before". Harmless, nothing is printed. | src/lib/buvis/pybase/updater/executor.py:134 | 1 | BLAKE |
| R14 | [1/4] | ⚪ | `index.py:61` calls `state_dir.mkdir(parents=True, exist_ok=True)` before every lookup. It is inside the `try` and needed so `cwd=state_dir` is valid, but the spec doesn't mention it. | src/lib/buvis/pybase/updater/index.py:61 | 0 | BLAKE |
| R15 | [1/4] | ⚪ | `index.py:11` imports `_query_pypi` by name, so a test patching `checker._query_pypi` does not affect `fetch_installable_version`. Production behaviour is correct; this only affects how tests must patch. | src/lib/buvis/pybase/updater/index.py:11 | 0 | BLAKE |
| R16 | [1/4] | ⚪ | `src/lib/buvis/pybase/configuration/click_integration.py:180` changes a docstring ("Force-check PyPI" to "the installer's index"). It isn't in the spec but is accurate and harmless. | src/lib/buvis/pybase/configuration/click_integration.py:180 | general | BLAKE |
| R17 | [1/4] | ⚪ | The state helpers do an unlocked read-modify-write on `updater.json`. Concurrent CLI runs can lose a field, but writes are atomic and the spec accepts the existing writer's behaviour. | src/lib/buvis/pybase/updater/state.py:110 | 0 | BLAKE |
| R18 | [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: test_returns_one_and_prints, test_logs_error_event | tests/lib/pybase/updater/test_force_update.py | general | mech-check |
| R19 | [1/4] | 🟡 | 3 touched test(s) pass against the pre-change code: test_returns_when_no_update_available, test_backoff_expires_after_24h, test_newer_version_than_failed_retries | tests/lib/pybase/updater/test_init.py | general | mech-check |

## Dispositions (standalone: reported, not written as tasks)

Verified against the code and the computed mechanical facts.

- **Fix (rework):** R1 (+R8, R10): confirmed by the computed sizes (`force_update` 57, `run_update` 70, `run_update_interactive` 59). R2 (+R9): the `or` hedge in a touched test is real. R4: `read_installed_version` parse/failure branches lack direct tests. R6: PRD only fails `--update` when the version is verified unchanged, so `None` printing "Upgraded." is PRD-silent, but it breaks the PRD's "honest `--update`" intent; print an unverified notice instead of plain success. R11: cheap, check `returncode` before parsing.
- **Fix if touched anyway:** R5 (private cross-module imports), R12 (future `ts` bound), R3/Alice half (double `mise where`).
- **Downgraded / accepted:** R7 to ⚪: only a hand-edited file can hold a non-version string (writers store `Version`-validated lookups), and `_newer_or_none` then returns None, so the cost is up to 6h of skipped checks with no crash, same as the legacy `read_cache`. R3/Blake half: argv0 is the spec-prescribed source and the cost is one 24h back-off. R13-R17: accepted as reported (harmless or spec-consistent).
- **Mechanical replay rows:** R19 `test_backoff_expires_after_24h` and `test_newer_version_than_failed_retries` pin the retry branch, which base also takes; their counterpart `test_backed_off_version_skips_upgrade` fails at base, so the back-off is pinned. R18 and `test_returns_when_no_update_available` are pre-existing tests whose mocks were adjusted for the new call path: behavior-preserving by design. No action beyond R2.

## Alice

Seven findings (R1, R2, R3, R4, R5, R11, R12). Verdicts: R1 pass, R2 fail, R3 pass, R4 pass, R6 pass, R7 pass, R8 pass, R9 pass, R10 pass, R11 pass, R12 fail, R13 pass.

## Blake

Six ⚪ findings (R3, R13-R17); no spec violations. Ran the updater tests (142 passed) and mypy on the updater package (clean). B1-B19: all pass.

## Bob

After one retry (inlined). Five findings (R1, R2, R6, R7, R8), all in FIX; VERIFY and KNOWN empty, so no verification-check queue entry.

R1: fail
R2: fail
R3: pass
R4: pass
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

Backend copilot, model gemini-3.8-flash. Four findings (R1, R2, R9, R10). Verdicts: R2 fail, R12 fail, all others pass.

Verdict: 19 findings
Tests: 4884 passed, 3 failed, 16 skipped (suite run this cycle; the 3 failures are the known env-only tests: 2 klyreon identity, 1 postup collect)
