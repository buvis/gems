---
prd: docs/dev/project-management/prds/wip/00115-braid-port-skills-parity-v1.md
review: 1
date: 2026-11-05
head_sha: 29cc80fe80d461a0eff6d37aebd96e4f77beba40
codex_thread_id: 01a1aa59-c582-7950-922e-e9ddaa59357b
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 1da48a26
  carl: 6dd6e0bb
---

# Review: 00115-braid-port-skills-parity-v1

Diff range: `c46b3916c3af84a9b22fd5782c8db0356419cc88..29cc80fe80d461a0eff6d37aebd96e4f77beba40`

codex_rung_guard: not fired

Full review (cycle 1) of five completed tasks. Consensus engine: legacy. Pack: failed (engram pack exit 1: worktree not registered with gita); prompts carried the no-pack sentinel. Fail-first replay skipped (no `--replay-cmd`: a base worktree would need a full uv sync plus Rust build). Tautological-shape check: 67 test functions in 3 files, no `[MECH]` lines.

Test gate: the `review-stage` run used plain `uv run pytest` and printed no PASS/FAIL summary line (3 host-env failures in klyreon and postup, outside braid). `autopilot verify` then re-ran the full suite through a scratch runner that unsets GIT_AUTHOR_*/GIT_COMMITTER_*, uses a scratch XDG_STATE_HOME and a BUVIS_CONFIG_DIR with `roots: []` for postup (the documented env-noise isolation); result below. The klyreon pair also passes alone with GIT_AUTHOR_* unset; the branch touches no klyreon or postup file.

Carl: backend copilot, model gemini-3.8-flash, exit 0.

Consolidation: script output, unchanged. Note: R1 and R5 are the same defect (UTF-8 decode errors escape the BraidError/OSError catch) cited at two files; R1's Found By lists BLAKE because the script folded Blake's compose.py:22 OSError-scope remark into it. The real voices on the defect are Alice and Bob.

Alice's resend for a missing R5 line returned `R5: pass`. The consensus rubric has no R5 (R1-R4, R6-R13), so her original output, which omits it, is the one consolidated.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | UnicodeDecodeError (a ValueError, not an OSError) from read_text on a non-UTF-8 sources.d file, .braidignore or SKILL.md escapes `except (BraidError, OSError)`. The user sees a traceback and the buffered report lines are dropped. This matches the reference, but AGENTS.md says raw exceptions must never reach the user. `_load_state` already maps UnicodeDecodeError. Fix: widen the catch in CommandCompose.execute to include UnicodeDecodeError, or wrap those reads in BraidError, and add one test. | src/tools/braid/commands/compose/compose.py:22 | 3 | ALICE, BLAKE |
| R2 | [1/4] | 🟠 | The Windows junction fallback passes filesystem paths through cmd.exe. subprocess argument-list quoting does not escape cmd metacharacters: a source directory such as C:\skills&calc& can execute calc when symlink privileges are unavailable. A future change should use junction creation without command-shell parsing. This is outside the parity port’s permitted changes because its contract explicitly requires create_directory_link to remain verbatim. | src/tools/braid/domain/engine.py:237 | 1 | BOB |
| R3 | [1/4] | 🟡 | Spec says the Phase 0 port changes only imports and `_write_state`, with `_sync_links` and `_report_orphans` kept as in the reference. The engine was refactored instead. `_sync_links` is split into `_remove_stale_links` plus `_Projection`/`_Pass` dataclasses, `_report_orphans` takes an `_OrphanScope`, and a `_project_host` helper is added. The shared types moved into an unlisted `domain/model.py`. Behaviour and line formats match the reference on a side-by-side read, and the ported suites pass, but the port is not "unchanged" and future diffs against agent-skills will be harder. | src/tools/braid/domain/engine.py:60 | 1 | BLAKE |
| R4 | [1/4] | 🟡 | `CommandCompose` takes a new `ComposeRequest` dataclass, not the `settings` the spec names. Source and policy resolution (`resolve_settings`, `_deduplicate`) lives in `domain/engine.py`, while the spec assigns it to the cli module. The domain is also no longer "pure composition" since it now holds the config-root and source discovery. Behaviour is unaffected. | src/tools/braid/commands/compose/compose.py:14 | 3 | BLAKE |
| R5 | [1/4] | 🟡 | Invalid UTF-8 in SKILL.md, sources.d, or .braidignore escapes as UnicodeDecodeError: their readers do not translate it, and execute() catches only BraidError/OSError. The CLI therefore loses its exit-2 error contract and can expose a traceback. Translate decoding failures into BraidError at each reader, including the offending path; add parametrized CLI tests asserting exit 2 and one diagnostic. | src/tools/braid/domain/engine.py:133 | 3 | BOB |
| R6 | [1/4] | ⚪ | `_sync_links` was split into `_remove_stale_links` and `_project_host`, which the contract does not name. The contract says only signatures change. Behavior is identical to reference cli.py:493-554, and the split is needed because the reference function is about 62 lines (R12). Record the deviation in the task report. | src/tools/braid/domain/engine.py:413 | 1 | ALICE |
| R7 | [1/4] | ⚪ | `test_cli_enrolls_kiro_from_the_environment` never asserts the exit code, so a CLI failure shows up only as a missing symlink. Add `assert result.exit_code == 0` for a clearer failure. | tests/tools/braid/test_cli.py:215 | 4 | ALICE |
| R8 | [1/4] | ⚪ | The spec says the `BraidError` message is printed "once through `console.failure`". `cli.py` instead calls `console.console.print(console.format_failure(escape(...)), soft_wrap=True)`, and the report lines go through `console.console.out`. Output is one marker line and the tests confirm it. It bypasses the named API, though, to get markup escaping and no wrapping. | src/tools/braid/cli.py:119 | 3 | BLAKE |
| R9 | [1/4] | ⚪ | `uv run mypy src/tools/braid` is clean, which meets the spec gate for `src/lib/` and `src/tools/`. Running mypy over `tests/tools/braid` reports 13 errors. They are in `helpers.py:47`, `test_engine.py:215`, `test_engine.py:239`, `test_engine.py:594`, `test_cli.py:18` and `test_cli.py:151`, and include the `OSError.winerror` and `Parameter.help` attribute errors. The repo gate does not cover tests, but the errors are real. | tests/tools/braid/test_cli.py:151 | 4 | BLAKE |
| R10 | [1/4] | ⚪ | `test_engine.py` has 33 test functions. The reference has 31 in `test_braid.py`, which gives about 26 engine cases once the CLI and parser cases are removed. Extra cases were added, such as `test_windows_junction_that_mklink_fails_to_create_is_an_error`. Some `test_cli.py` extras are not in the spec's list, including the dry-run, root-flag-wins, kiro-flag, forget, empty-kiro-env, ENOSPC and long-line cases. They are harmless extras, but the spec asked to "port, rewriting only imports and helpers". | tests/tools/braid/test_engine.py:1 | 2 | BLAKE |
| R11 | [1/4] | ⚪ | The spec names `conftest.py` as holding the `make_skill` and settings helpers. They are in a separate `tests/tools/braid/helpers.py`, and `conftest.py` holds only the autouse environment fixture. That fixture does delete every `BUVIS_BRAID_*` variable, as required. | tests/tools/braid/conftest.py:12 | 4 | BLAKE |

## Alice

[ALICE] ⚪ UnicodeDecodeError (a ValueError, not an OSError) from read_text on a non-UTF-8 sources.d file, .braidignore or SKILL.md escapes `except (BraidError, OSError)`. The user sees a traceback and the buffered report lines are dropped. This matches the reference, but AGENTS.md says raw exceptions must never reach the user. `_load_state` already maps UnicodeDecodeError. Fix: widen the catch in CommandCompose.execute to include UnicodeDecodeError, or wrap those reads in BraidError, and add one test. | File: src/tools/braid/commands/compose/compose.py:22 | Task: 3
[ALICE] ⚪ `_sync_links` was split into `_remove_stale_links` and `_project_host`, which the contract does not name. The contract says only signatures change. Behavior is identical to reference cli.py:493-554, and the split is needed because the reference function is about 62 lines (R12). Record the deviation in the task report. | File: src/tools/braid/domain/engine.py:413 | Task: 1
[ALICE] ⚪ `test_cli_enrolls_kiro_from_the_environment` never asserts the exit code, so a CLI failure shows up only as a missing symlink. Add `assert result.exit_code == 0` for a clearer failure. | File: tests/tools/braid/test_cli.py:215 | Task: 4

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

[BLAKE] 🟡 Spec says the Phase 0 port changes only imports and `_write_state`, with `_sync_links` and `_report_orphans` kept as in the reference. The engine was refactored instead. `_sync_links` is split into `_remove_stale_links` plus `_Projection`/`_Pass` dataclasses, `_report_orphans` takes an `_OrphanScope`, and a `_project_host` helper is added. The shared types moved into an unlisted `domain/model.py`. Behaviour and line formats match the reference on a side-by-side read, and the ported suites pass, but the port is not "unchanged" and future diffs against agent-skills will be harder. | File: src/tools/braid/domain/engine.py:60 | Task: 1
[BLAKE] 🟡 `CommandCompose` takes a new `ComposeRequest` dataclass, not the `settings` the spec names. Source and policy resolution (`resolve_settings`, `_deduplicate`) lives in `domain/engine.py`, while the spec assigns it to the cli module. The domain is also no longer "pure composition" since it now holds the config-root and source discovery. Behaviour is unaffected. | File: src/tools/braid/commands/compose/compose.py:14 | Task: 3
[BLAKE] 🟡 `CommandCompose.execute` catches `OSError` as well as `BraidError` and maps it to exit 2. The spec only names `BraidError` for exit 2, and the reference let a bare `OSError` traceback. This is safer, but it is behaviour beyond the spec and the reference. | File: src/tools/braid/commands/compose/compose.py:22 | Task: 3
[BLAKE] ⚪ The spec says the `BraidError` message is printed "once through `console.failure`". `cli.py` instead calls `console.console.print(console.format_failure(escape(...)), soft_wrap=True)`, and the report lines go through `console.console.out`. Output is one marker line and the tests confirm it. It bypasses the named API, though, to get markup escaping and no wrapping. | File: src/tools/braid/cli.py:119 | Task: 3
[BLAKE] ⚪ `uv run mypy src/tools/braid` is clean, which meets the spec gate for `src/lib/` and `src/tools/`. Running mypy over `tests/tools/braid` reports 13 errors. They are in `helpers.py:47`, `test_engine.py:215`, `test_engine.py:239`, `test_engine.py:594`, `test_cli.py:18` and `test_cli.py:151`, and include the `OSError.winerror` and `Parameter.help` attribute errors. The repo gate does not cover tests, but the errors are real. | File: tests/tools/braid/test_cli.py:151 | Task: 4
[BLAKE] ⚪ `test_engine.py` has 33 test functions. The reference has 31 in `test_braid.py`, which gives about 26 engine cases once the CLI and parser cases are removed. Extra cases were added, such as `test_windows_junction_that_mklink_fails_to_create_is_an_error`. Some `test_cli.py` extras are not in the spec's list, including the dry-run, root-flag-wins, kiro-flag, forget, empty-kiro-env, ENOSPC and long-line cases. They are harmless extras, but the spec asked to "port, rewriting only imports and helpers". | File: tests/tools/braid/test_engine.py:1 | Task: 2
[BLAKE] ⚪ The spec names `conftest.py` as holding the `make_skill` and settings helpers. They are in a separate `tests/tools/braid/helpers.py`, and `conftest.py` holds only the autouse environment fixture. That fixture does delete every `BUVIS_BRAID_*` variable, as required. | File: tests/tools/braid/conftest.py:12 | Task: 4

Verified by Blake: 85 braid tests pass, `pytest -m braid` scoped, `check_tool_wiring.py` exit 0, `sphinx-build -W` green, ruff clean, CLI surface complete, no `~/.config/agent-skills` fallback, no print in the domain, atomic state write, Kiro rewrite compare-before-replace, callback-level option rejections, implicit repo-root source removed.

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

Codex, inlined prompt (288 KB), exit 0.

[BOB] 🟡 Invalid UTF-8 in SKILL.md, sources.d, or .braidignore escapes as UnicodeDecodeError: their readers do not translate it, and execute() catches only BraidError/OSError. The CLI therefore loses its exit-2 error contract and can expose a traceback. Translate decoding failures into BraidError at each reader, including the offending path; add parametrized CLI tests asserting exit 2 and one diagnostic. | File: src/tools/braid/domain/engine.py:133 | Task: 3
[BOB] 🟠 The Windows junction fallback passes filesystem paths through cmd.exe. subprocess argument-list quoting does not escape cmd metacharacters: a source directory such as C:\skills&calc& can execute calc when symlink privileges are unavailable. A future change should use junction creation without command-shell parsing. This is outside the parity port’s permitted changes because its contract explicitly requires create_directory_link to remain verbatim. | File: src/tools/braid/domain/engine.py:237 | Task: 1

FIX:
- UTF-8 decode errors escape the exit-2 contract (above).

VERIFY:
- (none)

KNOWN:
- Windows junction fallback cmd.exe metacharacter injection (above).

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: fail
R8: fail
R9: pass
R10: fail
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend copilot, model gemini-3.8-flash.

[CARL] ✅ No issues found

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

Verdict: 11 findings
Tests: 6655 passed, 0 failed, 16 skipped (suite run this cycle)
