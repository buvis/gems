---
prd: docs/dev/project-management/prds/done/00115-braid-port-skills-parity-v1.md, docs/dev/project-management/prds/done/00116-braid-rules-kind-v1.md
review: 1
date: 2026-11-08
head_sha: b27b48b532f90cee9a974dcbcf12de27701c7b4a
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 84b52053
  carl: 05255974
---

# Review: feat/braid branch (PRDs 00115 + 00116), pre-merge

Diff range: `235a1d362344c895c30a2c12c37109426e7de6ce..b27b48b532f90cee9a974dcbcf12de27701c7b4a`

codex_rung_guard: not fired

## Review Summary

Reviewed: the whole `feat/braid` branch against master (28 product files, +5367/-4): the braid tool port (00115) and the rules kind (00116), both already converged in their own autopilot review cycles (batch 202611042342). No task list this cycle: `state.tasks` was emptied when the batch closed, so every finding is `Task: general`.
PRDs checked: 00115-braid-port-skills-parity-v1.md, 00116-braid-rules-kind-v1.md (staged as one spec with both design docs)

Scope note: this is a standalone, user-chosen branch review, not a PRD cycle. The skill reviews one PRD per run; the two PRDs here are consecutive halves of one feature on one branch about to merge, so both were staged as the requirements authority. `state.json` names 00116 (done); the single wip PRD, 00117, is master's fast-track PRD with a stale cycle-1 copy on this branch and was deliberately not reviewed. No autopilot state was written.

### Agent Status

- Alice: ✅ Available (native Claude subagent, legacy consensus engine)
- Blake: ✅ Available (native Claude subagent, blind)
- Bob: ✅ Available (codex, inlined prompt 403 KB, fresh thread; thread-id capture failed, so no `codex_thread_id`)
- Carl: ✅ Available (backend=copilot model=gemini-3.8-flash)

Notes:

- pack: failed (engram pack exit 1: not inside a registered repo). The review ran without the pack.
- Diff path-scoped after staging: `gather-context.sh --since` includes `docs/dev/project-management/` records (autopilot ledgers, prior reviews, reports, design docs), 2,700 lines of non-product diff. The staged diff and the context's changed-files block were regenerated with `:(exclude)docs/dev/project-management`; the mechanical facts (ast line counts over `.py` files) are unaffected.
- Fail-first replay skipped: no `--replay-cmd`. The branch adds a new tool, so every braid test fails on import against the base by construction. The tautological-shape block ran: 169 test functions in 7 files, no `[MECH]` lines.
- Test gate: the first staging run reported `counts unavailable` (exit 2, no summary). The gate runner's plain `uv run pytest -q` lost all pytest output after ~3% while the suite ran on (pytest's saved stdout was re-pointed at /dev/null), and the dot fixture's `git commit` hung on pinentry because the global gitconfig signs commits. Neither is braid's doing (the branch touches nothing under tests/lib or tests/tools/dot). `autopilot verify` with `uv run --no-sync pytest -q` and `commit.gpgsign=false` in the runner env then ran the full suite once at HEAD and recorded it; review-stage was re-run and reused that record. Same counts as the 00116 cycle-2 gate.
- Ledger: the settled ledgers of 00115 and 00116 (31 entries) were merged into `feat-braid-branch-ledger.json` and fed to Alice, Bob and Carl; Blake's re-raises were dismissed mechanically. Two dismissals matched on file rather than issue and are loose: the `render_host_file` empty-body re-raise (rules.py:183) is in the ledger under its own reason ("design contract drops empty bodies") but the printed reason is another entry's; the Windows backup-per-regeneration note (rules.py:313) matched the detached-hard-link entry, which is a different case. Both are single-voice Lows and would be discarded either way; listed below so the loose match is visible.
- No `checks-*.json` queue: standalone run, and no doubt lens emitted a VERIFY item with a command.
- Dispatch rows opened by hand (standalone staging opens none): bob 84b52053, carl 05255974, both closed `ok`.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | ⚪ | The per-file ruff ignore `PLR0913`/`PLR0917` for all of `rules.py` is wider than its comment. The comment justifies only `sync_rules`' six-parameter signature as the PRD contract, but the ignore also hides the 7 and 8 parameter private helpers (`_sync_generated`, `_sync_instruction_links`, `_sync_directory_hosts`). The engine took parameter objects instead of suppressing, so the two modules handle the lint differently. Narrow the ignore, or give the helpers the same `_Pass` and `_Projection` treatment as the engine. | pyproject.toml:187 | general | ALICE |
| R2 | [1/4] | ⚪ | Stale-removal for directory-host rule file links differs from skills. A recorded but hand-changed `<claude>/rules/<name>.md` is silently moved to backup in SYNC (drift +1), where skills raise "refusing to clean changed managed path". The PRD says "reusing the skills ... stale-removal logic", so this is an unrequested behavior fork. The backup keeps it recoverable | src/tools/braid/domain/engine.py:471 | general | BLAKE |
| R3 | [1/4] | ⚪ | Structure and scope drift from the PRD tree, with no functional harm found. The domain gains an unspecified `model.py`. `ComposeRequest` and `resolve_settings` (source and policy resolution the spec assigns to the cli layer) live in engine.py. `CommandCompose` also catches bare `OSError` as exit 2 (the spec says `BraidError`). Extra test files `test_file_links.py` and `test_rules_sync.py` exist, and `helpers.py` holds `make_rule`/`make_host_rule` instead of conftest.py. pyproject.toml:187 adds a per-file ruff ignore (PLR0913, PLR0917) for rules.py | src/tools/braid/domain/engine.py:580 | general | BLAKE |
| R4 | [1/4] | ⚪ | CLI help strings differ from the reference `_parser()` text ("copied from" in the spec). The edits are reasonable (env names, "skills and rules"), but they are not verbatim | src/tools/braid/cli.py:34 | general | BLAKE |

Disposition (standalone run, reported, not written as tasks): all four rows are single-voice Lows. R3 re-raises settled cycle-1 design decisions of 00115 (parameter objects, `ComposeRequest`, `OSError` to exit 2, helpers.py) already in the ledger under engine.py and model.py, so it survived the Blake filter only because it cites a new line. R2 is the one genuinely new observation: the rule file-link stale path backs up a hand-changed managed file where the skills path refuses; the backup makes it recoverable. R1 is a lint-scope nit with a two-line fix (narrow the per-file ignore to `sync_rules` or split the helpers' parameters). R4 is cosmetic. None blocks the merge.

### Auto-dismissed (ledger)

- [BLAKE] 🟡 Host instruction paths are hard-wired to Path.home() (~/.codex, ~/.copilot, ~/.pi, ~/.gemini) with no override flag or setting. A sync that uses tmp --agents-root/--claude-root (as the PRD 00115 exit-criteria example does) will still create or refresh links in the real home, pointing at the tmp generated file, whenever the host root exists and the path is absent. Read-only modes are safe. The spec fixes these paths, so this is a spec gap, but it is a data-safety and test-isolation hazard | File: src/tools/braid/domain/rules.py:290 — single-voice; PRD names the home paths and braid.rst documents that --agents-root runs still touch them
- [BLAKE] ⚪ A recorded host instruction path that the user later repoints to their own symlink counts as "owned" (recorded and is_symlink). Braid then backs it up and replaces it. The spec says a path braid does not own is never replaced or backed up, and "already a link braid recorded" is ambiguous about the target | File: src/tools/braid/domain/rules.py:300 — single-voice; design accepts UNMANAGED for a detached Windows hard link as the safe direction
- [BLAKE] ⚪ render_host_file drops empty or whitespace-only RULE.md bodies (`if body`). The spec says each eligible RULE.md is rendered and bodies are joined by one blank line, with no exclusion for empty bodies. Output differs from the literal spec only for empty rules | File: src/tools/braid/domain/rules.py:183 — single-voice; retiring rules is a documented manual step in braid.rst (remove the rules key and links by hand)
- [BLAKE] ⚪ An oversize generated file that also differs from disk counts two drifts on sync or check (GENERATE or MISMATCH GENERATED, plus OVERSIZE). The spec says "the run counts one drift" for oversize. The tests only cover the already-current case | File: src/tools/braid/domain/rules.py:270 — single-voice
- [BLAKE] ⚪ On Windows, each regeneration that detaches a hard-linked instruction file backs up the old link and relinks it. This creates a backup per RULE.md edit, and the spec does not mention it | File: src/tools/braid/domain/rules.py:313 — single-voice; design accepts UNMANAGED for a detached Windows hard link as the safe direction

## Alice

- R1 above (Low). Verified: `pytest tests/tools/braid` 254 passed, `mypy src/tools/braid` clean, ruff clean on braid src and tests, `check_tool_wiring.py` passes, `sphinx-build -W` passes. A scratch sync, check, remove-rule, sync, check cycle over a temp HOME with a shared rule, a Claude rule and a Codex rule gave 0 drift on the immediate check, removed the stale union link and regenerated the Codex file correctly.
- Verdicts: R1-R13 pass.

## Blake

- R2, R3, R4 above, plus five ledger-dismissed findings (one Medium, four Lows). Verified: `tests/tools/braid` 254 passed, `check_tool_wiring.py` clean, ruff clean, `mypy src/tools/braid` clean, `sphinx-build -W` exit 0, no `print(` in the domain, all PRD-named tests exist. Ported test_check has 12 of the reference's 13 cases (the CLI case moved to test_cli, the temp-cleanup case dropped, one new case added). Accepted the test-gate result rather than rerunning the suite.
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

- No issues found. Backend copilot, model gemini-3.8-flash. Ran the braid tests, `check_tool_wiring.py`, ruff, mypy and `sphinx-build -W` himself; all clean. R1-R13 pass.

Verdict: 4 findings
Tests: 6824 passed, 0 failed, 16 skipped (reused from last-verification.json at b27b48b)
