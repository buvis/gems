---
prd: docs/dev/project-management/prds/wip/00140-library-warnings-lack-marker-v1.md
review: 1
date: 2026-11-14
head_sha: fc27520de7cccc2d882210afaefad8a8678c51bb
codex_thread_id: 01a1d825-ac16-7a52-a163-8553f0e81222
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: b3b346c4
  carl: 6527c9a4
---

# Review: 00140-library-warnings-lack-marker-v1

Diff range: `cb2f1959dbfc2280ea2773039eee924db33ed8ae..fc27520de7cccc2d882210afaefad8a8678c51bb`

codex_rung_guard: not fired

Context pack: failed (engram pack exit 1: not inside a registered repo; `gita add` was not run for this worktree). The cycle ran degraded on the pack input only; both placeholders carried the `(no pack available this cycle)` sentinel.

Fail-first replay: skipped (runner produced no results, exit 1 from mise in the replay worktree). No replay evidence this cycle.

## Review Summary

Reviewed: 2 completed tasks
PRDs checked: 00140-library-warnings-lack-marker-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind lens, PRD-only)
- Bob: ✅ Available (codex, doubt lens + de-slop, exit 0)
- Carl: ✅ Available (gemini via copilot backend, exit 0)

No CRITICAL and no HIGH finding was raised by any lens. Every finding is Medium or Low.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | test_retired_twin_warning_deduped_across_two_invocations does not pin the handler's dedupe and does not assert the marker. It only counts "Retired config file" occurrences. `_warn_retired_twin` is already `@cache`-memoized (loader.py:32), so the count stays 1 with `_seen` removed. If the bare lastResort line is captured, it also stays 1 on pre-change code. Fix: assert the count of marked lines (the `⚠.*?Retired config file` regex used in the first test) across both invocations. Bind the handler's own dedupe with a non-cached message (for example the unsafe-path or unknown-key warning) through the real logger. | tests/lib/pybase/configuration/test_click_integration.py:1291 | 1 | ALICE, BOB |
| R2 | [2/4] | 🟡 | `_ConsoleWarningHandler.emit` reimplements `ConsoleAdapter.warning` (`console.console.print(console.format_warning(...), soft_wrap=True)`). The contract and PRD say to call `console.warning`. The deviation is justified in the assumptions ledger (Rich wraps long paths mid-message), but it reaches into the adapter's private Rich console and duplicates the marker/print logic. Simpler: give `ConsoleAdapter.warning` (or a small sibling) the `soft_wrap` behaviour and call that, so the marker stays defined in one place. | src/lib/buvis/pybase/configuration/click_integration.py:96 | 1 | ALICE, BLAKE |
| R3 | [2/4] | 🟡 | test_install_console_warning_bridge_is_idempotent removes pre-existing `_ConsoleWarningHandler`s (with their `_seen` state) and its `finally` removes the one it installed. It never restores the originals, so the bridge stays uninstalled for later tests in the session until another `@buvis_options` decoration runs. Restore the saved handlers in `finally`. | tests/lib/pybase/configuration/test_click_integration.py:1357 | 1 | ALICE, CARL |
| R4 | [1/4] | 🟡 | Bridge bypasses the required console adapter method using raw Rich output. Replace it with `console.warning(escape(message))`, tolerate wrapping in integration assertions, and spy on `console.warning` in the unit test. | src/lib/buvis/pybase/configuration/click_integration.py:96 | 1 | BOB |
| R5 | [1/4] | 🟡 | Installer test permanently removes pre-existing bridge handlers. Previously decorated commands invoked afterward can lose marked warnings. Preserve and restore the original handlers in `finally`. | tests/lib/pybase/configuration/test_click_integration.py:1346 | 1 | BOB |
| R6 | [1/4] | 🟡 | Mechanical check identifies an either-or assertion in `test_update_with_malformed_settings_exits_cleanly`. This test is unchanged and outside this PRD's warning-bridge scope. | tests/lib/pybase/configuration/test_click_integration.py:1073 | general | BOB, mech-check |
| R7 | [1/4] | 🟡 | test_update_with_malformed_settings_exits_cleanly hedges with or: either outcome satisfies it | tests/lib/pybase/configuration/test_click_integration.py:1073 | general | CARL, mech-check |
| R8 | [1/4] | ⚪ | `emit` has no try/except with `self.handleError(record)`, unlike stdlib handlers. A failure while printing (closed stdout, Rich error) propagates out of `logger.warning(...)` and aborts config resolution, which previously could not fail on a warning. | src/lib/buvis/pybase/configuration/click_integration.py:90 | 1 | ALICE |
| R9 | [1/4] | ⚪ | The new handler and installer have no docstrings. The contract's docstrings were dropped, including the load-bearing rationale for leaving `propagate` and `setLevel` untouched (`caplog` at root, `lastResort`). That rationale now lives only in the design doc, so a later editor of this code has no warning not to add `propagate = False`. | src/lib/buvis/pybase/configuration/click_integration.py:83 | 1 | ALICE |
| R10 | [1/4] | ⚪ | test_click_integration.py grows from about 1255 to about 1360 lines, well past the 800-line limit. The task said to append, so this extends an existing breach rather than starting one. Split `TestConsoleWarningBridge` into its own module when convenient. | tests/lib/pybase/configuration/test_click_integration.py:1262 | 1 | ALICE |
| R11 | [1/4] | ⚪ | The bridge logger keeps `propagate=True`, so a root handler would print the same record a second time. The dedupe lives only in the bridge handler, so the root copy is not deduped. `logging_to_console` in console.py:387 adds a root handler, but nothing under src/tools calls it, so this is latent today. The test with `--debug` passes because `--debug` does not install a root handler. | src/lib/buvis/pybase/configuration/click_integration.py:99 | general | BLAKE |
| R12 | [1/4] | ⚪ | Dedupe state `_seen` is an unbounded, unlocked set on a process-wide handler. Concurrent emits could print one message twice, and the set never shrinks. This is negligible for a CLI. | src/lib/buvis/pybase/configuration/click_integration.py:86 | general | BLAKE |
| R13 | [1/4] | ⚪ | The bridge is installed in `buvis_options()` at decoration time (import time of each tool), not when a command runs. It is still idempotent, and the tests cover this. The three tools that use the loader (braid, sysup, backup) all go through `buvis_options`, so they are covered. | src/lib/buvis/pybase/configuration/click_integration.py:463 | general | BLAKE |
| R14 | [1/4] | ⚪ | Test file exceeds the 800-line limit. The file already exceeded this limit, and the supplied task explicitly places additional tests here; splitting existing tests exceeds this review's scope. | tests/lib/pybase/configuration/test_click_integration.py:1262 | 1 | BOB |
| R15 | [1/4] | ⚪ | test_click_integration.py exceeds 800-line limit (1361 lines) | tests/lib/pybase/configuration/test_click_integration.py:1262 | 1 | CARL |
| R16 | [1/4] | ⚪ | _ConsoleWarningHandler and _install_console_warning_bridge lack docstrings explaining propagate and setLevel design rationale | src/lib/buvis/pybase/configuration/click_integration.py:83 | 1 | CARL |

Consolidation note: `consolidate_findings.py` produced this table. It merged R1's and R3's citations after line-suffix stripping (`:1291 ~ :1284`, `:1357 ~ :1359`). The single `[MECH]` tautological-shape line (the either-or assertion at test_click_integration.py:1073) matched rows R6 and R7, so `mech-check` was appended to both finders rather than adding a new row.

## Alice

Consensus lens, 6 findings (2 Medium, 4 Low) — see rows R1, R2, R8, R9, R10, R3 above.

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
R13: fail

## Blake

Blind lens (PRD-only prompt, found the code himself), 4 Low findings — rows R2, R11, R12, R13 above.

Checked and found compliant: the bridge sits in click_integration.py as the spec's structural decomposition requires; library output goes through the console adapter, imported lazily inside `emit`; loader.py is unchanged in API and its warning sites at lines 35, 438, 525 and 561 are untouched; the world-writable case is raised as `ConfigurationError` at loader.py:388 and surfaces through the "Skipping unsafe config path" warning, so the bridge covers it; dedupe is per process; the CHANGELOG `Fixed` entry is at CHANGELOG.md:29; the new CliRunner tests at tests/lib/pybase/configuration/test_click_integration.py:1263 cover the retired twin with exactly one ` ⚠ ` line, dedupe across two invocations, and `--debug`. He ran `-k ConsoleWarningBridge` (5 passed) and did not run the full suite.

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

## Bob

Doubt lens (codex, static-only sandbox) plus de-slop. FIX: rows R4, R1, R5. VERIFY: none. KNOWN: rows R6, R14.

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini lens (frontend & design specialist; generalist here, as this diff has no UI surface), 4 findings (2 Medium, 2 Low) — rows R7, R3, R15, R16 above. Backend: copilot.

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
R13: fail

## Follow-up Tasks Created

None by this skill (PRD 00249: task creation belongs to the decision gate).

Verdict: 16 findings
Tests: 7707 passed, 16 skipped, 1 xfailed, 10 errors (suite run this cycle at head_sha; counts read from docs/dev/tmp/gate-fc27520.log:1241 because `autopilot verify`'s summary parser does not recognise pytest's "errors" token and returned "counts unavailable" — a tooling gap, not a suite outcome. All 10 errors are pre-existing environment failures in tests/tools/dot/test_pull_divergence_two_hosts.py, unrelated to this diff.)
