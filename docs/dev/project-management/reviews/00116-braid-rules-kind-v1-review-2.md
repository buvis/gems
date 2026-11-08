---
prd: docs/dev/project-management/prds/wip/00116-braid-rules-kind-v1.md
review: 2
date: 2026-11-06
head_sha: 2afe11fdfc0d206ad24a0a1068f87692bd012335
codex_thread_id: 01a1adb5-5b3c-7bc2-b900-58da659ce670
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 47f45b0f
  carl: 8aadb7dd
---

# Review: 00116-braid-rules-kind-v1 (cycle 2, incremental)

Diff range: `38aa5eefdf28fd3c87901e5a8466dcd37d8d8af0..2afe11fdfc0d206ad24a0a1068f87692bd012335`

codex_rung_guard: not fired

## Review Summary

Reviewed: 6 completed tasks (incremental: task 6 rework, commits 13e2f590, afc62b00, 61215a95)
PRDs checked: 00116-braid-rules-kind-v1.md

### Agent Status

- Alice: ✅ Available (native Claude subagent, legacy consensus engine)
- Blake: ✅ Available (native Claude subagent, blind)
- Bob: ✅ Available (codex, inlined prompt, resumed thread 01a1adb5)
- Carl: ✅ Available (backend=copilot model=gemini-3.8-flash)

Notes:

- pack: failed (engram pack exit 1: not inside a registered repo; this worktree is not registered with gita). The review ran without the pack.
- Fail-first replay skipped: no `--replay-cmd` passed. The tautological-shape block ran: 21 test functions, no `[MECH]` lines.
- No `checks-1.json` queue exists, so nothing carries forward.
- The test gate parser reported `counts unavailable` for `pytest -q` output. The counts below come from the gate log `docs/dev/tmp/gate-202611052230.log`, line 145 (env-isolated full suite at HEAD 2afe11fd).
- Ledger auto-dismissal: the Blake finding about a re-pointed recorded symlink (rules.py:300) was matched to the settled Windows hard-link entry, which is a different case. It is a single-voice Low either way, so it would be discarded as `single-voice`; recorded here so the loose match is visible.
- Carl ran `mypy` over `tests/tools/braid` and saw type errors in test files. The project's mypy gate covers `src/lib/` and `src/tools/` only, and `mypy src/tools/braid` is clean (Blake and Carl both confirmed). Not a finding.

### Prior findings

- R1 (Windows foreign instruction file, 🟠): resolved. Ownership now needs a recorded path that is a symlink or in `detached` (pre-write `samefile`), rules.py:300. Regression test parametrized at tests/tools/braid/test_rules_sync.py:330. Alice and Bob confirm.
- R2 (keyword-only `emit`, 🟡): resolved. `*,` dropped at rules.py:427; positional test at tests/tools/braid/test_rules_sync.py:393. Alice and Bob confirm.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | ⚪ | `test_windows_separate_copy_of_unchanged_generated_file_at_a_recorded_path_is_unmanaged` passes against the pre-change code. Nothing regenerates in that run, so `host in regenerated` was already empty. It still guards the design rule that ownership is not content-based. It would be more convincing if it also asserted a check that fails before the fix, or if it were merged into the parametrized test as an unchanged-rule case. | tests/tools/braid/test_rules_sync.py:367 | 6 | ALICE |
| R2 | [1/4] | ⚪ | The `detached` capture runs on every platform, but only the `nt` branch reads it. It is harmless on POSIX, where it costs an extra `samefile` call. The comment at line 259 already says "Windows hard link", so no change is needed unless you want an explicit `platform == "nt"` guard. | src/tools/braid/domain/rules.py:261 | 6 | ALICE |
| R3 | [1/4] | ⚪ | An oversize file that also needs regeneration counts two drifts on sync (GENERATE plus OVERSIZE). The spec says "counts one drift" for oversize, which is ambiguous here. | src/tools/braid/domain/rules.py:255 | general | BLAKE |

### Auto-dismissed (ledger)

- [BLAKE] ⚪ Generated files are written with `atomic_write_bytes`, but the spec says `atomic_write_text`. | File: src/tools/braid/domain/rules.py:264 — single-voice; design deliberately overrides the PRD (CRLF on Windows)
- [BLAKE] ⚪ `render_host_file` silently drops empty or whitespace-only `RULE.md` bodies. | File: src/tools/braid/domain/rules.py:183 — single-voice; design contract drops empty bodies
- [BLAKE] ⚪ On sync, a pre-existing unrecorded `~/.agents/hosts/<host>/AGENTS.md` is moved to a backup before being overwritten. | File: src/tools/braid/domain/rules.py:257 — single-voice; design contract step 4 mandates the backup
- [BLAKE] ⚪ An instruction path that is a symlink braid recorded but that the user has since re-pointed elsewhere counts as owned. It is backed up and relinked, not reported UNMANAGED. | File: src/tools/braid/domain/rules.py:300 — single-voice; design accepts UNMANAGED for a detached Windows hard link as the safe direction
- [BLAKE] ⚪ When a host root is missing, the host's previous `instructions` state entry is not carried forward. | File: src/tools/braid/domain/rules.py:292 — single-voice; braid.rst documents the one-time MISMATCH STATE

## Alice

- Both prior findings resolved; no regression. R1, R2 (Lows above).
- Verdicts: R1-R13 pass.

## Blake

- R3 above, plus five ledger-dismissed Lows. Ran `pytest tests/tools/braid` (254 passed), `mypy src/tools/braid` (clean), ruff (clean).
- Verdicts: B1-B19 pass.

## Bob

- No issues found. FIX: none. VERIFY: none. KNOWN: none.

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

- No issues found. Backend copilot, model gemini-3.8-flash. R1-R13 pass.

Verdict: 3 findings
Tests: 6824 passed, 16 skipped, 1 xfailed (suite run this cycle)
