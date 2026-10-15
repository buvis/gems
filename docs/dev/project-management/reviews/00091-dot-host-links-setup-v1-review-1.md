---
prd: docs/dev/project-management/prds/done/00091-dot-host-links-setup-v1.md
review: 1
date: 2026-10-15
head_sha: bbabc93934660c4c708a502f71f51c87bc962835
codex_thread_id: 01a13f8d-e74c-7f22-82d6-b008aaabc124
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
  eve: disabled
---

# Review: 00091-dot-host-links-setup-v1

Diff range: `15d872fc6ca1fbb3d3a5a01f4418b686134b9d97..bbabc93934660c4c708a502f71f51c87bc962835`

codex_rung_guard: not fired

Run notes (standalone, no `state.json`):

- The PRD had already been moved to `prds/done/` (bbabc939) before review, and `prds/wip/` did not exist. This review targets the done PRD. No task store, so no task context.
- Consensus engine: legacy. Doubt reviewer: codex (Bob). Eve not active.
- pack: failed (engram pack exit 1: worktree not a registered gita repo). Prompts carried `(no pack available this cycle)`.
- Mechanical checks: no `[MECH]` lines. The fail-first replay was skipped (no pytest in the base worktree venv).
- Staging gate: `review-stage` ran the suite and could not parse counts (exit 1). The suite was rerun by hand; see `Tests:`.
- Consolidation: the script parsed Alice, Blake and Carl. Bob's lines carried a `- ` prefix and were not parsed, so his three rows were added by hand (format warning). His one retry was already used.

## Consolidated findings

| Ref | Consensus | Severity | Issue | File | Task | Found By | Disposition |
|-----|-----------|----------|-------|------|------|----------|-------------|
| R7 | [1/4] | 🟠 | Plain `cfg checkout` silently overwrites an existing untracked file that is ignored (for example by a pre-existing `~/.gitignore`). That breaks setup's "nothing overwritten" promise | src/tools/dot/commands/setup/setup.py:45 | general | BOB | **Fixed.** Reproduced with real git: an ignored `.zshrc` went `LOCAL` -> `tracked`, exit 0. Checkout now runs with `--no-overwrite-ignore`. Regression test `test_checkout_refuses_to_overwrite_an_ignored_existing_file` failed before the fix and passes after |
| R8 | [1/4] | 🟡 | hooksPath config write discards errors, so a failed write leaves `check_hooks()` silent | src/tools/dot/git/service.py:48 | general | BOB | **Rejected.** The PRD mandates the refspec self-heal pattern (which ignores write errors) and `hooks_path() None -> []`. A failed local `git config` write on a repo dot just opened would also fail every other git call |
| R1 | [2/4] | ⚪ | `git clone --bare <url>` has no `--`, so a URL starting with `-` is parsed as a git option (`--upload-pack=...`) | src/tools/dot/commands/setup/setup.py:31 | general | ALICE, BLAKE | **Fixed.** Clone is now `git clone --bare -- <url> <dir>`. Regression test `test_clone_treats_dash_leading_url_as_operand_not_option` failed before the fix |
| R6 | [2/4] | ⚪ | `tests/tools/dot/test_git_service.py` exceeds 800 lines (2335). It was already over the limit and this PRD added 94 lines | tests/tools/dot/test_git_service.py:1 | general | CARL, BOB | **Deferred.** Pre-existing. Splitting that suite is out of scope for this PRD |
| R2 | [2/4] | ⚪ | A step-4 `status.showUntrackedFiles` error becomes a warning; the PRD gives no error behavior for step 4 | src/tools/dot/commands/setup/setup.py:40 | general | ALICE, BLAKE | **Accepted as is.** Fails soft, tested, and matches the warn-and-continue style |
| R3 | [1/4] | ⚪ | `CommandMaterialize` gets `git_service=service`, which the PRD's call shape does not show | src/tools/dot/commands/setup/setup.py:54 | general | ALICE | **Accepted as is.** The kwarg exists and is covered by `test_materialize_installs_hooks_with_the_setup_service` |
| R4 | [1/4] | ⚪ | After a checkout conflict `.buvis` exists, so a rerun of `dot setup` refuses. The user must run `dot run checkout` and then `dot materialize` | src/tools/dot/commands/setup/setup.py:45 | CommandSetup | BLAKE | **Accepted as is.** Matches the PRD's step 1 and step 6, and the docs cover the recovery |
| R5 | [1/4] | ⚪ | `check_hooks` treats a non-executable or directory `pre-commit` as healthy (`exists()` only) | src/tools/dot/git/service.py:307 | Hook health warnings | BLAKE | **Accepted as is.** Matches the PRD literally |

Fixes applied in this review session (uncommitted at review-file write): `src/tools/dot/commands/setup/setup.py`, `tests/tools/dot/test_setup.py`, `tests/tools/dot/test_setup_real_git.py`, and `CHANGELOG.md` (the unreleased `dot setup` entry now says ignored files are refused too). After the fixes: `uv run pytest -m dot tests/tools/dot` gave 863 passed, 10 skipped, 1 xfailed. `uv run mypy src/tools/dot` reported no issues.

## Alice

Three ⚪ findings (R1, R2, R3). She ran `uv run pytest -m dot tests/tools/dot` (861 passed, 10 skipped, 1 xfailed) and did not run mypy.

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

## Blake

Four ⚪ findings (R1, R2, R4, R5). He traced every spec requirement to code. `uv run mypy src/tools/dot` was clean.

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

After one retry (inlined). On the first run the codex sandbox failed to start, so the output had the lack-of-input refusal shape. The retry produced R7, R8 and the R6 duplicate (format warning: lines prefixed `- `).

R1: fail
R2: pass
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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: copilot, model gemini-3.8-flash. One ⚪ finding (R6).

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

Verdict: 8 findings

Tests: 4877 passed, 3 failed, 16 skipped (suite run this cycle; 1 xfailed; the 3 failures are known env noise: 2 klyreon git-identity tests, 1 postup collect test calling real gh)
