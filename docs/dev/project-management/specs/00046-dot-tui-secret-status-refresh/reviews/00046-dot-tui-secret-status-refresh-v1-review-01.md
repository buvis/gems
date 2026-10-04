---
prd: dev/local/prds/wip/00046-dot-tui-secret-status-refresh-v1.md
review: 1
date: 2026-08-16
head_sha: b6a8cb75be9616797db9d1ead88a6296b09ddef7
codex_thread_id: 01a00905-aefc-7a10-9d57-25cd850a243c
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00046-dot-tui-secret-status-refresh-v1

Diff range: `a1c0e42b45c13dae4413a139f5c4b2a9ba0ad8f9..b6a8cb75be9616797db9d1ead88a6296b09ddef7`

codex_rung_guard: not fired

## Review Summary

Reviewed: 1 completed task
PRDs checked: 00046-dot-tui-secret-status-refresh-v1.md
Scope: full review (cycle 1, no prior cycle). Consensus engine: legacy. Doubt reviewer: codex (Bob).

### Agent Status

- Alice: ✅ Available (Claude subagent, implementation-aware consensus lens)
- Blake: ✅ Available (Claude subagent, blind lens — PRD only)
- Bob: ✅ Available (codex, consensus + doubt/de-slop lens)
- Carl: ✅ Available (gemini via copilot backend, frontend/UX specialist)

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟠 | Same-pattern check (bug-fix discipline): `has_uncommitted_changes()` still reads `cfg status --porcelain` with no hide, and app.py:84 uses it for the quit guard, so a secret changed after the last refresh does not count as uncommitted work when the user quits. | src/tools/dot/tui/git_ops.py | general | ALICE, BLAKE |
| [1/4] | 🟠 | Hide failure now blanks the entire TUI: `status()` raises so `refresh_status` returns before updating either pane, and `git secret hide -m` exits 1 in three reachable states — repo has no `.gitsecret` ("abort: directory '.gitsecret' does not exist"), initialized but no users told ("abort: no public keys for users found"), and a registered secret whose plaintext is missing (`force_continue` defaults to 0), i.e. any fresh clone before `git secret reveal`. Those users previously saw their whole file list and now see only an error; every other git-secret read in the TUI (`cfg secret list` in `status()` itself, `branch_info`, `list_secrets`) degrades gracefully instead. PRD-compliant fix: still read porcelain and show the hide error alongside the entries rather than instead of them. | src/tools/dot/tui/git_ops.py | 1 | ALICE |
| [1/4] | 🟡 | `refresh_status()` returns `None` on both success and failure, so the two callers that write `#diff` after it — `action_stage_hunk` (main.py:335-338) and `_do_revert` (main.py:371-374) — unconditionally overwrite the "Error refreshing status:" message with a fresh diff, leaving stale panes and no visible error; that is exactly the "silently show stale status" the PRD forbids, for any hide failure that starts mid-session. | src/tools/dot/tui/screens/main.py | 1 | ALICE |
| [1/4] | 🟡 | On hide failure `refresh_status` returns before `update_files`, so both panes keep the previous (stale) entries and the only signal is a string in the diff pane, which `on_file_list_widget_file_selected` overwrites on the next cursor move — the stale status becomes silent again, contradicting "does not silently show stale status" | src/tools/dot/tui/screens/main.py | Phase 0 | BLAKE |
| [1/4] | 🟡 | Fail-closed regression: the guard only proves the `git-secret` binary is on PATH, not that the repo is git-secret-initialised or that plaintexts were revealed; in those cases `secret hide -m` aborts, `status()` raises, and the TUI shows empty panes where it previously worked, with no degraded hide-less read | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | 🟡 | Regression test models the post-hide change as staged plaintext (`M  .ssh/config`), although hiding updates the unstaged ciphertext (` M .ssh/config.secret`); it therefore cannot prove the required first-render unstaged-pane behavior. | tests/tools/dot/test_git_ops.py:153 | 1 | BOB |
| [1/4] | 🟡 | `test_hide_failure_raises_and_skips_porcelain_status` uses a bare `pytest.raises(GitOpsError)`, so nothing pins that the shell's stderr reaches the message; the TUI test asserts on `GitOpsError("hide failed: disk full")` text it fabricates itself, so the stderr-to-user chain the PRD's second must-have depends on is untested. Add `match="permission denied"`. | tests/tools/dot/test_git_ops.py | 1 | ALICE |
| [1/4] | 🟡 | Extract lines 49-52 and the identical block in `commit()` (lines 98-101) into a `_hide_secrets()` helper that returns an optional error string to eliminate redundancy | src/tools/dot/tui/git_ops.py:49 | 1 | CARL |
| [1/4] | 🟡 | Two adjacent hide-error tests duplicate the same app setup and refresh sequence; merge them into one scenario asserting app survival, unchanged panes, and the displayed error. | tests/tools/dot/test_tui_app.py:347 | 1 | BOB |
| [1/4] | 🟡 | Success criterion "Issue #92 closed" is unmet: `gh issue view 92` reports state OPEN with `closedAt: null`, and the three fix commits are not on the remote (origin/master is fa574f1) — the fix exists only in the local branch | N/A | general | BLAKE |
| [1/4] | ⚪ | Docs unchanged: dot.rst:61 still bills `r` as "refresh all panes", but refresh is now a write (re-encrypts modified secrets on every one of the ~15 `refresh_status` call sites); dot.rst:87-88 likewise omits the hide step for `dot status`. | docs/source/tools/dot.rst | 1 | ALICE |
| [1/4] | ⚪ | `has_uncommitted_changes()` reads `status --porcelain` without hiding first; extracting the hide helper above would make it easy to fix this pre-existing gap where `action_quit` misses freshly modified secrets | src/tools/dot/tui/git_ops.py:145 | 1 | CARL |
| [1/4] | ⚪ | Test nit: `assert shell.exe.call_count == 1` followed by a loop asserting no call contains `cfg status --porcelain` is a double negative over a single call; `assert "cfg secret hide -m" in shell.exe.call_args_list[0][0][0]` says it once, positively. | tests/tools/dot/test_git_ops.py | 1 | ALICE |
| [1/4] | ⚪ | `status()` is now a mutating read path: every refresh shells out to gpg via `secret hide -m`, and `commit()` hides a second time immediately after the refresh that just hid — no dedup or throttle | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | ⚪ | `GitOps` now mixes two error conventions: `status()` raises `GitOpsError` while `stage`/`unstage`/`commit`/`pull`/`rm` all return `CommandResult`; the repo's own error rule discourages custom exception classes for control flow | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | ⚪ | Raw git-secret/gpg stderr is interpolated verbatim into the on-screen message, so gpg key ids and absolute paths reach the UI unfiltered and untruncated | src/tools/dot/tui/git_ops.py | Phase 0 | BLAKE |
| [1/4] | ⚪ | The changelog was committed separately from the fix, contrary to the repository rule requiring each fix commit to carry its changelog update. | CHANGELOG.md:38 | 1 | BOB |
| [1/4] | ⚪ | Cannot statically verify: dot tests pass. | N/A | 1 | BOB |

### Orchestrator notes on consolidation

- The `has_uncommitted_changes()` gap is really **3/4** (Blake 🟠, Alice ⚪, Carl ⚪). The script merged Alice and Blake and left Carl's wording as a separate ⚪ row because his `File:` carried a `:145` suffix.
- Alice's 🟠 "hide failure blanks the entire TUI" and Blake's 🟡 "fail-closed regression" are **one defect** (`status()` raising, `refresh_status` aborting before `update_files`), so that defect is **2/4**. They stayed separate rows because the wording differs. It is reworked once.
- Alice's 🟡 and Blake's 🟡 on the overwritten error message are likewise **one defect, 2/4**, seen from two trigger paths (post-action `#diff` writes vs. cursor movement).

## Alice

Implementation-aware consensus lens. Six findings: one 🟠, two 🟡, three ⚪ (see the table). Her 🟠 is the strongest evidence in the cycle — she enumerated three concrete `git secret hide -m` exit-1 states reachable on a normal machine, which turns "surface an error" into "show nothing but an error" for a fresh clone.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens (PRD only, no diff, no file list). Located the code himself and produced seven findings: one 🟠, three 🟡, three ⚪. Every blind rubric rule passed — the spec's three must-haves are all implemented; his findings are about reachable states and sibling paths the spec did not enumerate.

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

Codex, consensus + doubt/de-slop lens. Four findings: two 🟡, two ⚪. His test-realism finding is the cycle's most consequential one for the PRD itself: the regression test that is supposed to prove must-have #3 models the change as a **staged plaintext** (`M  .ssh/config`), but git-secret gitignores the plaintext and tracks the ciphertext, so real porcelain can only ever emit ` M .ssh/config.secret`. Independently confirmed by the orchestrator against this repo's own 00045 CHANGELOG entry ("The plaintext keeps its `.gitignore` entry").

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

### Doubt lens (FIX / VERIFY / KNOWN)

FIX:
- Regression test uses staged plaintext rather than the unstaged ciphertext produced by hiding — tests/tools/dot/test_git_ops.py:153 — model ` M .ssh/config.secret`, assert the returned ` M` entry, and verify it occupies the unstaged pane on initial render.
- TUI hide-error coverage duplicates setup and execution — tests/tools/dot/test_tui_app.py:347 — combine both tests into one scenario checking app survival, unchanged panes, and exception text.
- Changelog update is separated from its fix commit — CHANGELOG.md:38 — squash `b6a8cb7` into `a0f45b7` before merge.

VERIFY:
- Dot test suite result is unavailable under static-only review — run `uv run pytest -m dot` and require a passing result.

KNOWN:
- (none)

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini (copilot backend), frontend/UX specialist reviewing a Textual TUI. Two findings, both 🟡/⚪, and both about the same structural point: the hide block is now duplicated between `status()` and `commit()`, and a `_hide_secrets()` helper would both remove the duplication and make the `has_uncommitted_changes()` gap a one-line fix. All twelve consensus rubric rules pass.

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

## Decision gate (cycle 1)

Not converged: two unresolved 🟠 High findings remain. `state.cycle` (1) < `state.rework_cap` (2), so rework is allowed and the cap does not fire.

**Routed to rework (cycle 2):**

1. 🟠 Hide failure blanks the TUI — read porcelain regardless and surface the hide error *alongside* the entries. Also retires the mixed-error-convention ⚪.
2. 🟠 `has_uncommitted_changes()` missing the hide step (3/4) — fix via Carl's `_hide_secrets()` helper.
3. 🟡 `_hide_secrets()` extraction (dedup `status()`/`commit()`, enables #2).
4. 🟡 Hide-failure error message overwritten / stale panes (2/4).
5. 🟡 Regression test models staged plaintext instead of unstaged ciphertext.
6. 🟡 `pytest.raises` without `match=` — stderr-to-user chain untested.
7. 🟡 Merge the two duplicated hide-error TUI tests (preserving both assertions).
8. ⚪ `docs/source/tools/dot.rst` — `r` is now a write path; `dot status` hide step undocumented.
9. ⚪ Test nit: replace the double-negative assertion with the positive one.

**Settled deferrals and discards** (recorded in `dev/local/reviews/00046-dot-tui-secret-status-refresh-v1-ledger.json` and, for the deferrals, in the batch deferred JSON):

- 🟡 #92 still OPEN / commits unpushed — not a code defect; loop mode defers push and does not close issues.
- ⚪ double hide on refresh-then-commit — `hide -m` is incremental; dedup needs session state for no measurable gain.
- ⚪ raw gpg stderr in the UI — single-user local tool; verbatim stderr is what makes a hide failure diagnosable.
- ⚪ changelog in a separate commit — the entry exists; squashing rewrites made history for no user-visible gain.
- ⚪ **discarded** "Cannot statically verify: dot tests pass" — the orchestrator ran the suite (below); Bob's sandbox simply could not.

## Follow-up Tasks Created

1. Restore graceful degradation on hide failure and dedup the hide step (M) - 🟠 2/4 and 3/4 consensus - addresses items 1, 2, 3
2. Keep the hide-failure error visible instead of letting later writes bury it (S) - 🟡 2/4 consensus - addresses item 4
3. Make the secret-status tests model real porcelain and pin the stderr chain (M) - 🟡/⚪ consensus - addresses items 5, 6, 7, 9, and the dot.rst doc gap (item 8)

Suite run in the foreground by the orchestrator at `b6a8cb7` (`uv run pytest -q`, 28.7s). The 16 skips are the snapshot tests, auto-skipped off the canonical Linux/3.12 env; there is also 1 pre-existing xfail. No skip or xfail sits on this diff's code.

Verdict: 18 findings
Tests: 3919 passed, 0 failed, 16 skipped
