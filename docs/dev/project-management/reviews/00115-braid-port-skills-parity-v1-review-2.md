---
prd: docs/dev/project-management/prds/wip/00115-braid-port-skills-parity-v1.md
review: 2
date: 2026-11-05
head_sha: e8ce1d5fc0c5cf6ebff94713aa0c6bf3ca7d774c
codex_thread_id: 01a1aa59-c582-7950-922e-e9ddaa59357b
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: b3a5de11
  carl: 599ba17a
---

# Review: 00115-braid-port-skills-parity-v1

Diff range: `29cc80fe80d461a0eff6d37aebd96e4f77beba40..e8ce1d5fc0c5cf6ebff94713aa0c6bf3ca7d774c`

codex_rung_guard: not fired

Incremental review (cycle 2) of the cycle-1 rework: task 6 (Windows junction via `_winapi.CreateJunction`, commits 27f0a1c5, 1e058eae) and task 7 (non-UTF-8 input reported as exit 2 with the path, commit 4e60bef3). Consensus engine: legacy. Pack: failed (engram pack exit 1: worktree not registered with gita); prompts carried the no-pack sentinel. Fail-first replay skipped (no `--replay-cmd`). Tautological-shape check: 57 test functions in 2 files, no `[MECH]` lines. No prior verification-check queue (cycle 1 queued none).

Test gate: reused from `last-verification.json` at 4e60bef (env-isolated runner); HEAD e8ce1d5 differs from it only in autopilot store files.

Bob: codex, inlined prompt (169 KB), resumed thread 01a1aa59, exit 0.
Carl: backend copilot, model gemini-3.8-flash, exit 0.

Consolidation: script output, unchanged. No ledger auto-dismissals matched. Every row is a single Blake voice (Medium/Low). Prior R2 (cmd.exe injection) and R1/R5 (UTF-8 escape) are confirmed resolved by Alice and Bob; Blake's R1/R2 below object to those same fixes as departures from the verbatim-port contract.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟡 | Windows junction fallback was reimplemented: `create_directory_link` now calls `_winapi.CreateJunction` through an injected `junction` callable, where the reference ran `cmd /c mklink /J` through `runner`. The spec says "byte-for-byte", "junction fallback kept" and "changing only imports and `_write_state`". The ported Windows tests were rewritten to match. The change is arguably safer, but it is an unrequested behavior and signature change. | src/tools/braid/domain/engine.py:226 | 1 | BLAKE |
| R2 | [1/4] | 🟡 | Unrequested behavior beyond the port. `_read_lines` now also catches `UnicodeDecodeError` and turns unreadable skill, sources.d and policy files into `BraidError`. `CommandCompose` also catches bare `OSError`, so any filesystem error exits 2. The reference caught `BraidError` only, and the spec says "ported unchanged". Extra tests lock this in (test_cli_reports_a_non_utf8_input_file_on_one_line_and_exits_2, test_cli_reports_an_os_error_after_a_backup_and_exits_2). | src/tools/braid/domain/engine.py:133 | 1 | BLAKE |
| R3 | [1/4] | 🟡 | Structure deviates from the spec's module layout. The spec has `engine.py` and `kiro.py` as the only domain modules; there is an extra `domain/model.py` for the shared types. `_sync_links` and `_report_orphans` were refactored into `_Pass`, `_Projection` and `_OrphanScope` dataclasses. A new `ComposeRequest` dataclass and `resolve_settings` (source and policy resolution) live in the domain, though the spec assigns that work to `cli.py`. Tests pass, so behavior looks equivalent. | src/tools/braid/domain/model.py:1 | 1 | BLAKE |
| R4 | [1/4] | ⚪ | `BraidError` output goes through `console.console.print(console.format_failure(...), soft_wrap=True)` rather than `console.failure` as the spec states. Only the dry-run/check and `--no-kiro` rejections use `console.failure`. The output is still one line and the exit code is 2. | src/tools/braid/cli.py:119 | 3 | BLAKE |
| R5 | [1/4] | ⚪ | `__init__.py` has neither `__version__` nor `__all__`, which the spec's layout lists. Sibling tools are equally bare. `CommandCompose` takes a `ComposeRequest`, not the settings object the spec names. The `make_skill` and `settings` helpers are in `tests/tools/braid/helpers.py`, not `conftest.py`. The conftest autouse fixture does clear every `BUVIS_BRAID_*` variable. | src/tools/braid/__init__.py:1 | general | BLAKE |
| R6 | [1/4] | ⚪ | The `--dry-run` with `--check` rejection prints `--dry-run cannot be combined with --check` and exits 2 inside the callback, as specified. Nothing in the spec verifies the exact message, so I could not confirm it against the spec. | src/tools/braid/cli.py:90 | 3 | BLAKE |

## Alice

[ALICE] ✅ No issues found

Prior findings R1/R5 (non-UTF-8 input) and R2 (cmd.exe junction injection) are both resolved. `_read_lines` (src/tools/braid/domain/engine.py:133) wraps `OSError` and `UnicodeDecodeError` in `BraidError` with the path, used by `_skill_name`, `read_configured_sources` and `read_ignored`; the parametrized CLI test covers SKILL.md, sources.d and .braidignore. `create_directory_link` calls `_winapi.CreateJunction` through the `junction` seam, no `cmd` argv, `subprocess` no longer imported; the new metacharacter test forbids `subprocess.run`/`Popen`. Checks run: braid tests 89 passed, ruff clean, mypy clean.

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

[BLAKE] 🟡 Windows junction fallback was reimplemented: `create_directory_link` now calls `_winapi.CreateJunction` through an injected `junction` callable, where the reference ran `cmd /c mklink /J` through `runner`. The spec says "byte-for-byte", "junction fallback kept" and "changing only imports and `_write_state`". The ported Windows tests were rewritten to match. The change is arguably safer, but it is an unrequested behavior and signature change. | File: src/tools/braid/domain/engine.py:226 | Task: 1
[BLAKE] 🟡 Unrequested behavior beyond the port. `_read_lines` now also catches `UnicodeDecodeError` and turns unreadable skill, sources.d and policy files into `BraidError`. `CommandCompose` also catches bare `OSError`, so any filesystem error exits 2. The reference caught `BraidError` only, and the spec says "ported unchanged". Extra tests lock this in (test_cli_reports_a_non_utf8_input_file_on_one_line_and_exits_2, test_cli_reports_an_os_error_after_a_backup_and_exits_2). | File: src/tools/braid/domain/engine.py:133 | Task: 1
[BLAKE] 🟡 Structure deviates from the spec's module layout. The spec has `engine.py` and `kiro.py` as the only domain modules; there is an extra `domain/model.py` for the shared types. `_sync_links` and `_report_orphans` were refactored into `_Pass`, `_Projection` and `_OrphanScope` dataclasses. A new `ComposeRequest` dataclass and `resolve_settings` (source and policy resolution) live in the domain, though the spec assigns that work to `cli.py`. Tests pass, so behavior looks equivalent. | File: src/tools/braid/domain/model.py:1 | Task: 1
[BLAKE] ⚪ `BraidError` output goes through `console.console.print(console.format_failure(...), soft_wrap=True)` rather than `console.failure` as the spec states. Only the dry-run/check and `--no-kiro` rejections use `console.failure`. The output is still one line and the exit code is 2. | File: src/tools/braid/cli.py:119 | Task: 3
[BLAKE] ⚪ `__init__.py` has neither `__version__` nor `__all__`, which the spec's layout lists. Sibling tools are equally bare. `CommandCompose` takes a `ComposeRequest`, not the settings object the spec names. The `make_skill` and `settings` helpers are in `tests/tools/braid/helpers.py`, not `conftest.py`. The conftest autouse fixture does clear every `BUVIS_BRAID_*` variable. | File: src/tools/braid/__init__.py:1 | Task: general
[BLAKE] ⚪ The `--dry-run` with `--check` rejection prints `--dry-run cannot be combined with --check` and exits 2 inside the callback, as specified. Nothing in the spec verifies the exact message, so I could not confirm it against the spec. | File: src/tools/braid/cli.py:90 | Task: 3

Verified by Blake: braid tests 89 passed, `check_tool_wiring.py` OK, `braid --help` lists every reference option, no print in the domain, settings and env prefix match, docs and CHANGELOG present, atomic state write, Kiro compare-before-replace. Not run by Blake: sphinx-build, full suite.

B1: pass
B2: pass
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

Codex, inlined prompt (169 KB), resumed thread, exit 0.

[BOB] ✅ No issues found

FIX:
- (none)

VERIFY:
- (none)

KNOWN:
- (none)

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

Verdict: 6 findings
Tests: 6659 passed, 0 failed, 16 skipped (reused from last-verification.json at 4e60bef)
