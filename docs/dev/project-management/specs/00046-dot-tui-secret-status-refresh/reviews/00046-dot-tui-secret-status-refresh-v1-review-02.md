---
prd: dev/local/prds/wip/00046-dot-tui-secret-status-refresh-v1.md
review: 2
date: 2026-08-16
head_sha: b66e9c970476a734b438574c0b5389528959bf86
codex_thread_id: 01a00905-aefc-7a10-9d57-25cd850a243c
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00046-dot-tui-secret-status-refresh-v1

Diff range: `b6a8cb75be9616797db9d1ead88a6296b09ddef7..b66e9c970476a734b438574c0b5389528959bf86`

codex_rung_guard: not fired

## Review Summary

Reviewed: 3 completed tasks (1 original-plan, 2 cycle-1 `[D1]` decision-gate follow-ups)
PRDs checked: 00046-dot-tui-secret-status-refresh-v1.md
Scope: incremental review (cycle 2, rework since cycle 1's head `b6a8cb7`). Consensus engine: legacy. Doubt reviewer: codex (Bob), resumed on his cycle-1 thread.

**All 13 cycle-1 findings verified resolved.** The rework then introduced a new build-breaking regression and three new High defects, so the cycle does not converge.

### Agent Status

- Alice: ✅ Available (Claude subagent, implementation-aware consensus lens)
- Blake: ✅ Available (Claude subagent, blind lens — PRD only)
- Bob: ✅ Available (codex, consensus + doubt/de-slop lens; resumed thread `01a00905`)
- Carl: ✅ Available (gemini via copilot backend, frontend/UX specialist)

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🔴 | Snapshot mock never updated to the new `status()` tuple contract: `ops.status.return_value = staged + unstaged` returns a 33-item list, so all 10 dot snapshot tests crash with `ValueError: too many values to unpack (expected 2)` at main.py:141 on the canonical env (ubuntu + py3.12), which is exactly what CI's tools job runs — the PRD success criterion "dot tests green" is unmet there, and the local run hides it behind 10 skips | tests/tools/dot/test_tui_snapshots.py:57 | 2 | ALICE, BLAKE |
| [1/4] | 🟠 | The hide error is silently invisible at common widths: `StatusBar` is `height: 1` (main.py:74) and Rich wraps the appended error onto a clipped second row, so with the project's own fixture branch info an 80-col terminal renders none of the error while both panes populate normally (verified via `export_screenshot`: 40/60/80 cols hide it, 100+ shows it; multi-line stderr always loses every line but the first) — PRD must-have 2 fails in the most common terminal size, reproducing the "silently show stale status" the PRD forbids | src/tools/dot/tui/widgets/status_bar.py:48 | 3 | ALICE |
| [1/4] | 🟠 | Hide error is appended raw to a 1-row docked StatusBar with no truncation or wrapping; at 80x24 a realistic multi-line git-secret/gpg error renders as only "git-secret: abort: problem" and with a long branch name it is clipped entirely off-screen, so the stale-status hole the PRD closes silently returns | src/tools/dot/tui/widgets/status_bar.py | Phase 0 | BLAKE |
| [1/4] | 🟠 | Hide-error tests assert on `status_bar.content.plain` (the model string), never on rendered output, so they pass even when zero characters of the error are visible to the user — the must-have "TUI surfaces the error" is untested as a user-visible fact | tests/tools/dot/test_tui_app.py | Phase 0 | BLAKE |
| [1/4] | 🟠 | Out-of-spec: `has_uncommitted_changes()` now runs `cfg secret hide -m` and discards the error, so the quit guard mutates the work tree and fails open — a failed hide leaves porcelain clean and the TUI lets the user quit with an unencrypted secret change unreported (repo rule: never silently swallow errors) | src/tools/dot/tui/git_ops.py | general | BLAKE |
| [1/4] | 🟠 | Quit guard discards hide failures, so failed encryption plus clean stale porcelain exits without confirmation despite a changed plaintext secret; treat hide failure as an unsafe/unknown state requiring confirmation. | src/tools/dot/tui/git_ops.py:140 | 2 | BOB |
| [1/4] | 🟡 | `has_uncommitted_changes()` calls `self._hide_secrets()` and discards the returned error, so when re-encryption fails the quit guard reads the stale ciphertext, reports "clean" and exits with no prompt and no signal anywhere; `test_hide_failure_with_clean_porcelain_returns_false` pins that silent outcome as intended | src/tools/dot/tui/git_ops.py:142 | 2 | ALICE |
| [1/4] | 🟡 | Diverges from the CLI it is told to mirror: `CommandStatus` aborts with `CommandResult(success=False)` on hide failure, the TUI renders the stale panes as authoritative with no stale marker, dimming, or pane-level warning | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | 🟡 | Guard is only `is_command_available("git-secret")`; in a dotfiles repo with git-secret installed but not initialized, every refresh runs a failing `git secret hide -m` and paints a permanent red error in the status bar plus a wasted subprocess per refresh | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | 🟡 | Hide now fires on all ~12 `refresh_status()` paths (mount, stage, unstage, delete, ignore, commit, push, pull, hunk apply, revert, modal dismiss, `r`) synchronously on the Textual event loop with no worker, so every staging keystroke blocks the UI on a gpg/bash subprocess | src/tools/dot/tui/screens/main.py | Phase 0 | BLAKE |
| [1/4] | 🟡 | The freshly-hidden secret shows as `.ssh/config.secret` but never gets the `[secret]` badge: `is_secret` matches porcelain ciphertext paths against `git secret list` plaintext paths, which can never match; the new tests document the mismatch and leave it, so the PRD's user-visible goal lands half-delivered | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | 🟡 | Rework pushes `test_tui_app.py` beyond the 800-line limit; move the hunk-staging and revert test classes into focused modules. | tests/tools/dot/test_tui_app.py:786 | 3 | BOB |
| [1/4] | 🟡 | UX correctness: StatusBar has `height: 1`, so a multi-line `hide_error` (e.g. from GPG) will be vertically truncated, hiding diagnostic info. Single-line format the error before appending (e.g. `self._error.strip().replace("\n", " ")`) or allow the bar to expand. | src/tools/dot/tui/widgets/status_bar.py | 2 | CARL |
| [1/4] | ⚪ | `test_commit_success_message_not_overwritten_by_hide_error_refresh` only asserts the hide error is absent from `#diff`; it never asserts the error reached the status bar, so the commit path's error-surfacing is unpinned and the test would still pass if the error vanished entirely | tests/tools/dot/test_tui_app.py:434 | 3 | ALICE |
| [1/4] | ⚪ | `test_status_bar.py` has one focused test per rendered field (ahead, behind, secret count, and their zero cases) but no test for the new error branch or for `error=None` clearing it; both are only covered indirectly through full-app tests | tests/tools/dot/test_status_bar.py | 3 | ALICE |
| [1/4] | ⚪ | `test_tui_app.py` grew 739 → 804 lines this cycle, crossing the 800-line file max; splitting the four hide-error TUI tests into their own module restores it | tests/tools/dot/test_tui_app.py | 3 | ALICE |
| [1/4] | ⚪ | `status()` now calls `is_command_available("git-secret")` twice per invocation (was once), and `branch_info()` on the same refresh adds a third check plus a second `cfg secret list` | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | ⚪ | Error text is surfaced unprefixed and unfiltered; when git-secret aborts on stdout the ShellAdapter drops it and returns `str(CalledProcessError)`, so the status bar can show "Command '...' returned non-zero exit status 1." — meaningless to the user, and unlike the CLI which concatenates stdout | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | ⚪ | Churn-artifact test asserts absence of `GitOpsError`, a class that only ever existed inside this change's own intermediate commits; it binds to implementation history, not behavior, and can never fail for a business-logic reason | tests/tools/dot/test_git_ops.py | general | BLAKE |
| [1/4] | ⚪ | Docs edit rewrites the `dot status` CLI description (pre-existing behavior) alongside the TUI change — outside PRD scope, harmless but unrequested | docs/source/tools/dot.rst | general | BLAKE |
| [1/4] | ⚪ | Changelog incorrectly says hide failure no longer leaves displayed status stale; porcelain can remain stale, while the actual fix is that the failure is no longer silent. | CHANGELOG.md:38 | 3 | BOB |

### Orchestrator notes on consolidation

- The 🔴 snapshot break is **2/4** (Blake 🔴, Alice 🟠). Consolidation merged them and kept the higher severity. **The orchestrator independently reproduced it** (below) — this is confirmed, not suspected.
- The StatusBar visibility defect is really **3/4** (Alice 🟠, Blake 🟠, Carl 🟡). The merger left Alice's and Blake's as separate rows because the wording differs, and Carl's as a third because he framed it as multi-line truncation rather than clipping. One defect, reworked once.
- The quit-guard defect is **3/4** (Blake 🟠, Bob 🟠, Alice 🟡) — same split-by-wording cause. One defect.
- Blake's 🟡 `is_secret` badge row restates the cycle-1 **settled deferral** on `FileEntry.is_secret` (ledger entry 6). The `--ledger-dismiss BLAKE` matcher did not catch it (different wording), so the gate excludes it by hand. It does not block convergence either way.

### Verification performed by the orchestrator (not delegated)

- **Full suite, foreground, at `b66e9c9`:** `uv run pytest -q` → **3926 passed, 0 failed, 16 skipped, 1 xfailed** (29.97s).
- **The 16 skips are load-bearing, not noise.** 10 of them are the dot TUI snapshot tests, auto-skipped off the canonical env (macOS here). Forcing the canonical gate reproduces the crash exactly:
  `uv run env BUVIS_SNAPSHOT_CANONICAL=1 pytest tests/tools/dot/test_tui_snapshots.py -q -x` → **1 failed** (stopped at first), stderr showing `ValueError: too many values to unpack (expected 2)` raised from `MainScreen.on_mount` → `refresh_status` at `src/tools/dot/tui/screens/main.py:141`.
  `.github/workflows/test.yml` runs the tools job on `ubuntu-latest` × Python 3.12 — the canonical snapshot env — where the skip does not apply. **CI is red on this branch.**
- Both Alice and Blake independently forced the same gate and independently reported 10/10 failures with the identical traceback.
- Working tree left clean (the forced snapshot runs write `snapshot_report.html` at the repo root; removed).

## Alice

Implementation-aware consensus lens. Verified all 13 prior findings resolved with file:line evidence for each, then found 6 new issues: two 🟠, one 🟡, three ⚪. Her strongest contribution is the empirical status-bar visibility probe — she drove a real `DotApp` through `export_screenshot` at 40/60/80/100/120 columns and established that at 80 columns, with the project's own fixture branch info, **no part of the hide error renders** while both panes populate normally. That turns "we surface the error" into "we surface it only on wide terminals", which is PRD must-have 2 failing in the common case.

She also declined to flag two things, correctly: the 53-line `on_diff_view_revert_requested` (pre-existing, untouched by this diff — surgical scope) and the double `is_command_available` probe (cheap `shutil.which`; every alternative shape adds a parameter).

R1: pass
R2: pass
R3: fail
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: fail

## Blake

Blind lens (PRD only, no diff, no file list, no review history). Found the code himself and produced 12 findings: one 🔴, four 🟠, four 🟡, four ⚪ — the widest net this cycle, and he is the only reviewer who rated the snapshot break Critical.

Three blind rules failed. B1 (implementation satisfies all specified behaviors) and B5 (specified error-handling behaviors) both fail on the status-bar visibility defect; B6 (no functionality beyond the PRD) fails because `has_uncommitted_changes()` now mutates the work tree — the PRD scopes the hide step to `GitOps.status()` only.

His verification discipline was explicit: he ran `-m dot` (446 passed, 10 skipped), noticed the 10 skips were the snapshot tests, forced the canonical gate, got 10/10 failures, and traced the workflow file to confirm CI runs that leg. He also probed the rendered status bar via `render_line` rather than reading CSS, and cleaned up his own `snapshot_report.html`.

B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
B6: fail
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

Codex, consensus + doubt/de-slop lens, resumed on his cycle-1 thread (`01a00905-aefc-7a10-9d57-25cd850a243c`), so he verified his own cycle-1 critique rather than re-reviewing from zero. Three findings: one 🟠, one 🟡, one ⚪. He did not re-raise the settled deferrals, and — notably — did not re-emit last cycle's "Cannot statically verify: dot tests pass", which the ledger recorded as discarded.

His 🟠 independently reaches Blake's quit-guard conclusion from the safety side rather than the spec side: a hide failure plus clean stale porcelain is an *unknown* state, and the guard treats it as *clean*. His proposed fix is to return a conservative dirty/unknown outcome so `action_quit()` still prompts.

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: fail

### Doubt lens (FIX / VERIFY / KNOWN)

FIX:
- Quit guard treats a hide failure followed by clean porcelain as no uncommitted work — src/tools/dot/tui/git_ops.py:140 — preserve `_hide_secrets()`'s result and return a conservative dirty/unknown outcome so `action_quit()` requires confirmation; invert the clean-porcelain failure test and cover the quit prompt.
- Rework makes the TUI app test file at least 804 lines — tests/tools/dot/test_tui_app.py:786 — move `TestMainScreenHunkStaging` and `TestMainScreenRevert` into focused test modules.
- Changelog overstates graceful degradation as eliminating stale status — CHANGELOG.md:38 — restore "silently" or state that available porcelain remains displayed alongside a persistent hide error.

VERIFY:
- (none)

KNOWN:
- (none)

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini (copilot backend), frontend/UX specialist on a Textual TUI. Verified all cycle-1 findings resolved and raised one 🟡: the same `StatusBar height: 1` defect Alice and Blake found, framed as multi-line truncation, with a concrete fix (single-line-format the error before appending, or let the bar expand). All twelve consensus rubric rules pass — he is the only reviewer who passed R9/R10, having judged the error-surfacing correct at the model layer without probing the rendered output.

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

## Decision gate (cycle 2)

**Not converged, and the cap is reached.** `state.cycle` (2) >= `state.rework_cap` (2), and one unresolved 🔴 Critical remains after exclusions.

Exclusions applied per the cap check: settled deferrals (the `is_secret` badge row) and prior-cycle discards are not counted. Medium and Low findings never block convergence. That leaves:

- **1 🔴 Critical** — the snapshot-mock contract break. Orchestrator-reproduced; CI is red.
- **3 distinct 🟠 High defects** (6 rows before de-duplication) — status-bar invisibility (3/4), quit guard failing open (3/4), and hide-error tests binding to the model string rather than rendered output.

A Critical is never a settled deferral, so it blocks. In loop mode a cap-out with an unresolved Critical **stalls the PRD** (`site: cap_critical`) and the batch continues — it does not pause the batch and does not finalize with deferrals.

**Outcome: PRD 00046 stalls to `dev/local/prds/hold/`. The batch drains on.**

No follow-up tasks were created in the tracker: the stall's per-PRD reset clears `state.tasks`, and leftover TaskList entries would make the next PRD's Phase 2 skip planning. The rework plan is recorded here instead, for whoever un-parks it.

### Rework plan on un-park (in priority order)

1. **🔴 Fix the snapshot mock contract.** `tests/tools/dot/test_tui_snapshots.py:57` — `ops.status.return_value = (staged + unstaged, None)`. One line. Then verify with `uv run env BUVIS_SNAPSHOT_CANONICAL=1 pytest tests/tools/dot/test_tui_snapshots.py`. **Also sweep for other stale callers of the changed `status()` contract** — this bug class is "a contract changed and a mock didn't", and the local skip hid it.
2. **🟠 Make the hide error actually visible.** `StatusBar` is `height: 1`; decide between letting the bar expand, single-line-collapsing the error (`err.strip().replace("\n", " ")`) with truncation and a marker, or a dedicated error row. Must hold at 80x24 with a long branch name and a multi-line gpg error.
3. **🟠 Stop the quit guard failing open.** `has_uncommitted_changes()` discards `_hide_secrets()`'s error; on failure return a conservative dirty/unknown so `action_quit()` still prompts. Invert `test_hide_failure_with_clean_porcelain_returns_false`, which currently pins the unsafe behavior as intended.
4. **🟠 Bind the hide-error tests to rendered output**, not `status_bar.content.plain` — otherwise fix 2 cannot be proven and can regress silently.
5. The 🟡/⚪ tail (CLI-divergence stale marker, uninitialised-repo guard, sync gpg on the event loop, `test_tui_app.py` over 800 lines, changelog wording, missing `StatusBar` error unit tests) rides along with the above.

**Note on scope:** finding 2 is a genuine design question (how a 1-row status bar surfaces a multi-line error), not a mechanical fix. That is the main reason this is a stall rather than one more rework pass.

Verdict: 21 findings
Tests: 3926 passed, 0 failed, 16 skipped
