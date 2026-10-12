---
prd: docs/dev/project-management/prds/wip/00088-dot-host-links-materialize-v1.md
review: 1
date: 2026-10-12
head_sha: 053e3cea29d5f172db1c7e92e4fa3e08d0731cc1
codex_thread_id: 01a1317a-8517-7081-a4d6-d0f5b8b7b9ea
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: 46698b6a
  carl: e5e8907f
---

# Review: 00088-dot-host-links-materialize-v1

Diff range: `231719bd23f31594d4ac9dd7d530d4a327609dd2..053e3cea29d5f172db1c7e92e4fa3e08d0731cc1`

codex_rung_guard: not fired

Cycle: 1 (full review). Consensus engine: legacy.

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database). Reviewers ran without the context pack.

Fail-first replay: skipped (runner produced no results: ModuleNotFoundError: No module named '_pytest'). Tautological test shapes: no `[MECH]` lines.

## Review Summary

Reviewed: 9 completed tasks
PRDs checked: 00088-dot-host-links-materialize-v1.md

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available, after one retry (inlined). The first codex run could not read any file (`sandbox-exec`: `sandbox_apply: Operation not permitted`) and returned an empty, all-fail review (dispatch row 0f653ffd, lack-of-input).
- Carl: ⚠️ Unavailable: copilot backend (gemini-3.8-flash) `Authentication failed`, exit 1 on the first run and on the one retry. One-off runtime failure, not exit 4, so not latched for the batch.

## Consolidated Findings

Consolidation: `consolidate_findings.py` for Alice and Blake. Bob's three findings were added to the table by hand (R13-R15, format warning): he wrote them as `- [BOB] ...` bucket bullets, which the script does not parse, and his retry budget was already spent.

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/3] | 🟡 | Unrelated postup frontend build artifacts are in the diff: 19 deleted and 8 modified files under the build directory. They are uncommitted working-tree churn from another task and have no connection to PRD 00088. Drop them from this change (restore or exclude them) so the dot feature commit stays scoped. | src/tools/postup/adapters/web/frontend/build/_app/version.json | general | ALICE |
| R2 | [1/3] | 🟡 | `CommandMaterialize` takes an extra `git_service` keyword argument that the spec's signature `CommandMaterialize(shell, dotfiles_root, *, install_hooks=True)` does not have. The TUI passes it, and tests use it for injection. | src/tools/dot/commands/materialize/materialize.py:22 | 4 | BLAKE |
| R3 | [1/3] | 🟡 | `README.md` has only a one-line mention of `host-links` (line 95). The spec says both docs describe the manifest format, `dot materialize`, the hooks and the Windows Developer Mode note. `docs/source/tools/dot.rst` covers all four. The literal `rg host-links` check passes. | README.md:95 | 6 | BLAKE |
| R4 | [1/3] | ⚪ | `_read_link` strips `\\?\` with a plain `removeprefix`. A junction target of `\\?\UNC\server\share` becomes the relative-looking `UNC\server\share`, so the link would be reported as "links to elsewhere". Design review item d3 flagged this and it was never addressed. Map `\\?\UNC\` to `\\` first. | src/tools/dot/hostlinks/linker.py:24 | 2 | ALICE |
| R5 | [1/3] | ⚪ | If writing a later hook raises `OSError`, `install_hooks` loses the "installed hook <name>" lines for hooks already written, because the exception propagates and the caller only adds `hooks: <exc>`. Design review item d3 flagged this and it is not addressed. Either collect lines before re-raising, or accept and document it. | src/tools/dot/hostlinks/hooks.py:47 | 3 | ALICE |
| R6 | [1/3] | ⚪ | The docs say existing hook files are never changed. They do not warn that a pre-existing non-dot `post-checkout`, `post-merge` or `post-rewrite` hook silently stops relinking, and dot never reports it. This was design question d1. Add one sentence to the Host-specific config section. | docs/source/tools/dot.rst:1029 | 9 | ALICE |
| R7 | [1/3] | ⚪ | The new tests for `hooks_path` and the TUI `L` key live in new files (`test_git_service_hooks_path.py`, `test_tui_host_links.py`). The task text said to append them to `test_git_service.py` and `test_tui_app.py`. The coverage is complete, so this is only a placement deviation. | tests/tools/dot/test_tui_host_links.py:1 | 8 | ALICE |
| R8 | [1/3] | ⚪ | `hooks_path()` joins a relative `core.hooksPath` onto the work tree. The spec only says to expand `~`. | src/tools/dot/git/service.py:285 | 4 | BLAKE |
| R9 | [1/3] | ⚪ | `_is_absolute` also rejects any path with a root component (for example `\foo`) through `windows.root != ""`. This is slightly broader than the spec's list. The result is still "absolute path". | src/tools/dot/hostlinks/manifest.py:29 | 1 | BLAKE |
| R10 | [1/3] | ⚪ | `read_manifest` returns an extra error `host-links: <exc>` for an unreadable or undecodable manifest. `CommandMaterialize` wraps hook-install `OSError` as a `hooks: <exc>` warning. Neither is in the spec. Both fail soft and are reasonable. | src/tools/dot/hostlinks/manifest.py:94 | 1 | BLAKE |
| R11 | [1/3] | ⚪ | `install_hooks` checks that the hook is missing and then calls `atomic_write_text`, which does `os.replace`. A hook created in between would be silently replaced, though the window is tiny. | src/tools/dot/hostlinks/hooks.py:46 | 2 | BLAKE |
| R12 | [1/3] | ⚪ | `install_hooks` also skips a dangling symlink and creates `hooks_dir` if it is missing. Both are safe additions beyond the spec's "when the file is missing". | src/tools/dot/hostlinks/hooks.py:42 | 2 | BLAKE |
| R13 | [1/3] | 🟡 | Documentation tells users to keep host files "in the repo," recreating the cross-host sharing this feature prevents. State that the manifest is tracked and host-local sources remain untracked. (format warning) | docs/source/tools/dot.rst:211 | 9 | BOB |
| R14 | [1/3] | 🟡 | Directory-link tests require `is_symlink()`, but Windows deliberately creates junctions, which fail that assertion. Assert directory accessibility and resolved destination across platforms; check symlink type only on POSIX. (format warning) | tests/tools/dot/test_materialize.py:46 | 6 | BOB |
| R15 | [1/3] | 🟡 | The TUI test checks only the first mocked display call, so it cannot establish that the materialize message survives `refresh_status()`. Run a TUI test with a nonempty file list and an unmocked DiffView; press L, await refresh, and assert the final displayed message contains `linked <target>`. (format warning; VERIFY bucket, not queued: names no single runnable command) | tests/tools/dot/test_tui_host_links.py:83 | 8 | BOB |

## Alice

Raw output: `docs/dev/tmp/alice-output-202610121845.txt`. Findings R1, R4-R7. Evidence: `uv run pytest tests/tools/dot` 757 passed, 10 skipped, 1 xfailed; `uv run mypy src/tools/dot` clean.

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

Raw output: `docs/dev/tmp/blake-output-202610121845.txt`. Findings R2, R3, R8-R12. No Critical or High.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: fail
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

After one retry (inlined). Raw output: `docs/dev/tmp/bob-output-202610121845.txt`. Findings R13-R15 (FIX: R13, R14; VERIFY: R15; KNOWN: none).

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
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Unavailable: copilot `Authentication failed` (exit 1), first run and one retry. No output consolidated.

Verdict: 15 findings
Tests: 4770 passed, 3 failed, 16 skipped (suite run this cycle; the 3 failures are known env noise: 2 klyreon identity tests, 1 postup collect test)
