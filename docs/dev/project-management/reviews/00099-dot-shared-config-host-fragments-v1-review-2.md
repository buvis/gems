---
prd: docs/dev/project-management/prds/wip/00099-dot-shared-config-host-fragments-v1.md
review: 2
date: 2026-10-19
head_sha: 8248d727d5c8080836ee90c2be9b3ce72492ef58
codex_thread_id: 01a152f2-dba7-7262-9aa1-35a4bbf7a425
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 3f5120d5
  carl: 5c153beb
---

# Review: 00099-dot-shared-config-host-fragments-v1 (cycle 2)

Diff range: `3a405b235ee75a9e1bae436d47f52c4a78d0467a..8248d727d5c8080836ee90c2be9b3ce72492ef58` (incremental — the rework since cycle 1)

codex_rung_guard: not fired

## Review Summary

Reviewed: 10 completed tasks
PRDs checked: 00099-dot-shared-config-host-fragments-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens, legacy engine)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens)
- Bob: ✅ Available (codex, doubt + de-slop lens, resumed cycle-1 thread)
- Carl: ✅ Available (gemini via copilot backend, UI/design lens) — reported no issues

Staging notes:
- Engram context pack: ok.
- Tautological-shape check: no `[MECH]` findings for this diff.
- Settled-decisions ledger passed to consolidation with `--ledger-dismiss BLAKE`; no Blake finding was auto-dismissed.
- Test gate: the full suite exits 1 in this sandbox. The 3 failures (klyreon identity x2, postup collect) are the known environment noise; the 10 errors in `tests/tools/dot/test_pull_divergence_two_hosts.py` are `git commit` exit 128 caused by the sandbox's forced ssh commit signing (`GIT_CONFIG_*` env injection). Carl re-ran that file with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_NOSYSTEM=1` and it passes; Blake ran this PRD's seven test files green (299 passed). Neither is a defect in this diff.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟠 | Docs now contradict the code. `docs/source/tools/dot.rst:419` says dot "rolls the attribute line (and the index entry) back when the renormalize or the staging step fails, and says so in the error". The rework keeps the registration on stage failure and returns a success result with a warning. It also does not document the new refusals (newline/CR in the path, symlinked or non-regular `.gitattributes`). Update the paragraph and the refusal list at `dot.rst:407-417`. | docs/source/tools/dot.rst:419 | 7 | ALICE, BLAKE |
| R2 | [2/4] | 🟠 | Stage-failure behavior now follows the PRD clause. The task 3 spec and design doc required a full rollback. Their stated reason was a real correctness defect: `renormalize` has already put the tokenized blob in the index, so a failed `.gitattributes` stage followed by a commit pushes tokens without the attribute. The cycle-1 gate chose the PRD wording. The new code leaves that exposure behind a warning only. Record the conflict, or keep the exposure explicit in the docs and the warning text. | src/tools/dot/commands/localize/share.py:284 | 7 | ALICE, BOB |
| R3 | [2/4] | 🟡 | `DotGitService.restore_index_entry` now has no production caller. `CommandShare` only calls `capture_index_entry`. The method is dead code kept alive only by service tests. Either drop it or note why it stays. `test_never_restores_target_index_entry_on_stage_success` (`tests/tools/dot/test_share.py:605`) and `restore_index_entry.assert_not_called()` (`test_share.py:684`) are vacuous: they pass against the pre-change code and cannot fail as written. | src/tools/dot/git/filter_driver.py:144 | 7 | ALICE, BLAKE |
| R4 | [1/4] | 🟠 | Configured driver values differ from the spec. The spec requires `filter.dot-host.clean = BUVIS_AUTO_UPDATE=false dot filter clean %f` (and the matching smudge); the code writes `... dot filter clean -- %f`. The `--` is reasonable hardening but unspecified, and it is baked into tests and docs. | src/tools/dot/git/filter_driver.py:33 | 2 | BLAKE |
| R5 | [1/4] | 🟡 | Either-or hedge assertion in the symlink-refusal test (`tests/tools/dot/test_share.py:891`): `any(word in message for word in ("symlink","refus","regular","plain"))`. The message is deterministic, so assert it exactly, and assert the symlink target still holds its original text. | tests/tools/dot/test_share.py:891 | 7 | ALICE |
| R6 | [1/4] | 🟡 | The FIFO regression test asserts only `not result.success` and mocks `Path.is_file`, so it never touches a real FIFO. Assert the exact `_NOT_PLAIN` error and that `.gitattributes` was not created; a real `os.mkfifo` is safe now. | tests/tools/dot/test_share.py:905 | 7 | ALICE |
| R7 | [1/4] | 🟡 | Simplification: `ls_files` hand-rolls single-quoting for the leading-dash case to satisfy a pinned test string. Use `cfg ls-files -- {shlex.quote(pathspec)}` for all inputs and update the pinned assertions; this removes the branch, the duplicate command and the custom quoting. | src/tools/dot/git/service.py:419 | 10 | ALICE |
| R8 | [1/4] | 🟡 | Unspecified refusals and checks in `CommandShare` ("driver not configured", "non-regular index mode", "uncapturable index entry", the `check-attr` conflicting-attribute refusal with rollback). Defensive and sensible, but scope creep beyond the spec's refusal set. | src/tools/dot/commands/localize/share.py:119 | 3 | BLAKE |
| R9 | [1/4] | 🟡 | Out-of-scope edit to `DotGitService.ls_files`: a special case for leading-dash pathspecs with hand-rolled quoting made to satisfy a pinned test string. | src/tools/dot/git/service.py:419 | 2 | BLAKE |
| R10 | [1/4] | 🟡 | `normpath()` removes symlink-bearing components before confinement checks. With `a` pointing outside the root, `a/../settings` now silently selects the root's `settings` instead of refusing the original outside path. Validate the original path and reject symlink traversal before collapsing `..`; add this regression case. | src/tools/dot/commands/localize/share.py:90 | 7 | BOB |
| R11 | [1/4] | 🟡 | The whitespace refusal remains incomplete: adding newline and CR still permits vertical tab and form feed, contrary to the required all-whitespace rejection. Use `str.isspace()` alongside the punctuation check and add these cases. | src/tools/dot/commands/localize/share.py:29 | 7 | BOB |
| R12 | [1/4] | 🟡 | `ls_files` now duplicates command construction and hand-rolls shell quoting solely to satisfy a new exact-string assertion. Replace both branches with `cfg ls-files -- {shlex.quote(pathspec)}` and assert parsed arguments in tests. | src/tools/dot/git/service.py:419 | 7 | BOB |
| R13 | [1/4] | 🟡 | Removing `_index_mode` leaves obsolete `_index_read`/`canned_index_read` mock-shell machinery: index reads now use the injected service. Remove those helpers and their assignments, using a plain mock shell. | tests/tools/dot/test_share.py:21 | 7 | BOB |
| R14 | [1/4] | ⚪ | `tests/tools/dot/test_share.py` is 805 lines, over the 800-line limit. Split off the new classes or drop dead helpers. | tests/tools/dot/test_share.py:805 | 7 | ALICE |
| R15 | [1/4] | ⚪ | Ordering change: `capture_index_entry` now runs before the token, glob, quoting and driver checks. An unreadable or conflicted index entry now reports "not a plain tracked file" ahead of those more specific refusals. Behavior is safe; only the error priority changed. | src/tools/dot/commands/localize/share.py:119 | 7 | ALICE |
| R16 | [1/4] | ⚪ | Structure deviation: `_ensure_filter_driver` and `renormalize` live in `src/tools/dot/git/filter_driver.py` as a mixin `DotGitService` inherits; the spec's layout lists only `service.py`. Behavior and public surface match. | src/tools/dot/git/service.py:23 | 2 | BLAKE |
| R17 | [1/4] | ⚪ | `CommandShare` counts host values with `count_home(data, str(self._root))` while the filter derives home from GIT_WORK_TREE, cwd, DOTFILES_ROOT or `Path.home()`. The dry-clean count could differ under a symlinked root. The spec does not pin a resolver. | src/tools/dot/commands/localize/share.py:278 | 3 | BLAKE |
| R18 | [1/4] | ⚪ | Test-gate observation: the full suite exits 1 with no summary line in this sandbox, so the full-suite state is unverified from the gate alone. This PRD's seven test files pass (299), as do mypy, ruff, the sphinx build and the docs assertion script. | N/A | general | BLAKE |

### Decision-gate merges (judgment call on issue text plus file)

- R7 + R9 + R12 — `ls_files` hand-rolled quoting for the leading-dash case — ALICE, BLAKE, BOB
- R3 + R8 — the unused `restore_index_entry` / capture-entry machinery beyond the spec — ALICE, BLAKE

### Decision-gate dispositions

- Cap-overflow deferrals (cycle 2 of 2, rework cap reached): R1, R2.
- Settled deferral carried from cycle 1, not re-litigated: R4 (requirements ambiguity, the `--` in the driver commands).
- Discarded as single-voice Medium/Low: R5, R6, R10, R11, R13, R14, R15, R16, R17, R18.
- Kept as multi-voice Medium: R3 (with R8), R7 (with R9, R12) — deferred with the cap overflow.

## Alice

Consensus lens, implementation-aware, incremental. Verified cycle-1 findings R1, R2/R18, R3, R5, R6, R7/R12, R8/R16/R17, R13/R19, R14/R20 as resolved. Eight new findings (R1, R2, R3, R5, R6, R7, R14, R15 above).

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

Blind lens, PRD only. Found the implementation himself; eight findings (R1, R4, R3, R8, R9, R16, R17, R18 above). Reported the transforms, the `dot filter` plumbing, driver registration, shared localize and the real-Git tests as spec-compliant.

B1: fail
B2: fail
B3: pass
B4: pass
B5: pass
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

Doubt lens + de-slop (codex, resumed cycle-1 thread). FIX: R2, R10, R11, R12, R13. VERIFY: (none). KNOWN: (none).

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
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

UI/design lens (gemini via copilot backend). No issues found. Independently re-ran the dot suite with an isolated git config, which confirmed the `test_pull_divergence_two_hosts.py` errors are sandbox signing noise.

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

Verdict: 18 findings
Tests: 5562 passed, 3 failed, 16 skipped, 1 xfailed, 10 errors (suite run this cycle; the 3 failures and 10 errors are known sandbox environment noise, not defects in this diff)
