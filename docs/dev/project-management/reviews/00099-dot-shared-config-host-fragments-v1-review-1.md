---
prd: docs/dev/project-management/prds/wip/00099-dot-shared-config-host-fragments-v1.md
review: 1
date: 2026-10-19
head_sha: 3a405b235ee75a9e1bae436d47f52c4a78d0467a
codex_thread_id: 01a152f2-dba7-7262-9aa1-35a4bbf7a425
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 726a418a
  carl: 3625688c
---

# Review: 00099-dot-shared-config-host-fragments-v1

Diff range: `09e0c01b4ce68f28940d0fdebf01aa882964ab11..3a405b235ee75a9e1bae436d47f52c4a78d0467a`

codex_rung_guard: not fired

## Review Summary

Reviewed: 6 completed tasks
PRDs checked: 00099-dot-shared-config-host-fragments-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens, legacy engine)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens)
- Bob: ✅ Available (codex, doubt + de-slop lens)
- Carl: ✅ Available (gemini via copilot backend, UI/design lens)

Staging notes:
- Engram context pack: ok.
- Fail-first replay: `replay: skipped (runner produced no results (exit 1: … No module named pytest))` — the replay worktree's venv lacks pytest under the sandbox. No replay evidence this cycle.
- Tautological-shape check: no `[MECH]` findings for this diff.
- No settled-decisions ledger exists yet (cycle 1), so `--ledger`/`--ledger-dismiss` were not passed to consolidation.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | `src/tools/dot/commands/localize/__init__.py` now exports `CommandShare` and imports `share.py` eagerly. The PRD module contract says "lazy import by CLI without changing the plain localize package exports", and the design says the same for the CLI. Importing the package now pulls `DotGitService` and `hostlinks.manifest` on every `dot localize` and in any test that imports `CommandLocalize`. Revert this file; `cli.py` already imports `CommandShare` lazily from `dot.commands.localize.share`. | src/tools/dot/commands/localize/__init__.py:3 | 3 | ALICE, BOB, CARL |
| R2 | [2/4] | ⚪ | `resolve_home` does not strip trailing separators on a Windows-spelled home. The contract says to strip `/` and, on the Windows-spelling path, `\`. `str(Path(...))` on POSIX leaves `C:\Users\bob\` alone, so `_pattern` then requires a trailing separator and `smudge` writes `C:/Users/bob/` plus the suffix. The trailing-separator tests (test_hostfilter.py:304, 307) only cover POSIX. Add `rstrip("/\\")` for the Windows-spelled branch and a test. | src/tools/dot/hostfilter.py:57 | 1 | ALICE, BLAKE |
| R3 | [1/4] | 🟠 | Stage-failure behavior contradicts the spec. The spec says an attribute stage failure keeps the shared registration and index and returns a warning containing `run 'dot add .gitattributes'`. `_roll_back` instead undoes the attribute line and restores the index entry, and returns success=False with "share rolled back, retry 'dot localize --shared ...'". The warning string never appears. Tests (tests/tools/dot/test_share.py:656-760) and docs (docs/source/tools/dot.rst:419) encode the rollback, so they would not catch the deviation. | src/tools/dot/commands/localize/share.py:279 | 3 | BLAKE |
| R4 | [1/4] | 🟠 | The configured driver commands differ from the exact values in the spec. The spec requires `BUVIS_AUTO_UPDATE=false dot filter clean %f` and `... smudge %f`. The code writes `... dot filter clean -- %f` and `... smudge -- %f`. The test and docs pin the `--` variant, so the "exact three config values" acceptance for the service task is not met as written. | src/tools/dot/git/filter_driver.py:33 | 2 | BLAKE |
| R5 | [1/4] | 🟠 | `.gitattributes` is opened without confinement or symlink checks. A symlink can read outside the root and have its contents copied into the tracked registry; rollback cannot restore the original link. Reject symlinked or non-regular registries before reading or writing. | src/tools/dot/commands/localize/share.py:105 | 3 | BOB |
| R6 | [1/4] | 🟠 | A tracked file replaced by a FIFO passes the existing filesystem checks and blocks in `read_bytes()`. The index-mode check runs afterward and would still report the formerly regular file. Check the work-tree entry with `lstat()` and require a regular file before reading; add a FIFO regression. | src/tools/dot/commands/localize/share.py:113 | 3 | BOB |
| R7 | [1/4] | 🟡 | `CommandShare` cannot share a tracked path that starts with `-`, which the PRD's shell-unsafe-path requirement says must work. `execute` checks tracking with `DotGitService.ls_files`, which runs `cfg ls-files <pathspec>` with no `--` and no `:(literal)` prefix. For `-dashy.conf` git rejects the argument as an option, the set comes back empty, and the user gets the misleading "not tracked; run dot add first". `tests/tools/dot/test_shared_real_git.py:322` documents this and works around it by writing `.gitattributes` and renormalizing by hand, so nothing tests the PRD scenario through `CommandShare`. Fix: check tracking with a literal pathspec after `--` (for example through `capture_index_entry`) and add a real-git test that shares `-dashy.conf` via `CommandShare`. | src/tools/dot/commands/localize/share.py:145 | 3 | ALICE |
| R8 | [1/4] | 🟡 | Redundant ls-files parsing and literal-pathspec quoting in the diff. `CommandShare._index_mode` (share.py:230) repeats the `cfg ls-files -s -- <literal>` call and stage-0 parsing of `FilterDriverMixin.capture_index_entry` (filter_driver.py:134). `execute` then issues the same call a second time through `capture_index_entry` (share.py:120). Capture once and test `entry.mode in _REGULAR_MODES`, which also deletes the third inline `shlex.quote(f":(literal)...")` copy at share.py:232 and the `test_reads_index_mode_with_a_pathspec_for_the_target` special case. `service.py` also now imports the private `_literal` from `filter_driver`; make it a public name or keep it in one place. | src/tools/dot/commands/localize/share.py:230 | 3 | ALICE |
| R9 | [1/4] | 🟡 | Scope creep in the share action, beyond the spec's refusal and rollback set. It adds `check_attr_filter` (a conflicting-attribute check that triggers rollback), a `filter_driver_configured()` refusal, `capture_index_entry` and `restore_index_entry` index rollback, and a "not a plain tracked file / index mode" refusal. These are defensible hardening, but none are specified and they cause the stage-failure deviation above. | src/tools/dot/commands/localize/share.py:171 | 3 | BLAKE |
| R10 | [1/4] | 🟡 | Structure deviates from the spec. The driver logic (`_ensure_filter_driver`, `renormalize`, plus the extra methods) lives in a new mixin file `filter_driver.py`, and `IndexEntry` was added to `models.py`. The spec places these in `DotGitService` in service.py. `DotGitService` still exposes them by inheritance, so behavior is unaffected. | src/tools/dot/git/filter_driver.py:37 | 2 | BLAKE |
| R11 | [1/4] | 🟡 | Driver rollback removes only keys written successfully during this invocation. Pre-existing smudge/required keys survive a failed installation, contradicting the fully-inert rollback contract. Attempt cleanup of all three keys and test failures with pre-existing partial configuration. | src/tools/dot/git/filter_driver.py:65 | 2 | BOB |
| R12 | [1/4] | 🟡 | Leading-dash opt-in remains broken, and the integration test bypasses it by writing `.gitattributes` manually. Add the missing `--` to `DotGitService.ls_files`, update its pinned assertion, and exercise `CommandShare` for `-dashy.conf`. | tests/tools/dot/test_shared_real_git.py:334 | 5 | BOB |
| R13 | [1/4] | 🟡 | The quoting check rejects only space and tab, allowing newline-bearing filenames to inject additional attribute records. The effective-filter check does not prevent this when an existing wildcard already assigns dot-host to the target. Reject all whitespace before mutation and add newline/CR cases. | src/tools/dot/commands/localize/share.py:28 | 3 | BOB |
| R14 | [1/4] | 🟡 | Relative input retains its original spelling, so `./settings` produces `/./settings filter=dot-host` and fails attribute matching. Normalize the root-relative pathname before registry comparisons and attribute generation while preserving symlink refusals; test equivalent path spellings. | src/tools/dot/commands/localize/share.py:95 | 3 | BOB |
| R15 | [1/4] | 🟡 | The two-host pull test creates B after sharing, leaving the required first arrival of `.gitattributes` and tokenized content untested. Create B before A shares, give B its local home-valued content, then assert the first pull's bytes, index, divergence recovery, and subsequent clean pull. | tests/tools/dot/test_shared_real_git.py:272 | 5 | BOB |
| R16 | [1/4] | 🟡 | `_index_mode` duplicates the service's stage-zero parser and executes Git directly from the command layer. Use one captured `IndexEntry` for mode validation and rollback; remove the duplicate parser, shell dependency, and tests that require the redundant call. | src/tools/dot/commands/localize/share.py:230 | 3 | BOB |
| R17 | [1/4] | 🟡 | Simplification: _index_mode duplicates capture_index_entry git query and line parsing | src/tools/dot/commands/localize/share.py:226 | 3 | CARL |
| R18 | [1/4] | 🟡 | resolve_home does not normalize Windows backslashes or strip trailing backslash separators | src/tools/dot/hostfilter.py:55 | 1 | CARL |
| R19 | [1/4] | ⚪ | `_QUOTE_CHARS` is `" \t#!\\"` and omits `\n` and `\r`. Git ends an attribute pattern at a blank, so a tracked path containing a newline would write a second attribute line that applies to a different file name. `check_attr_filter` and the rollback catch this, so nothing is left behind. The user still gets the misleading "conflicting attribute entry" error instead of the quoting refusal. Add `\n\r` to the set, or use `str.isspace`. | src/tools/dot/commands/localize/share.py:28 | 3 | ALICE |
| R20 | [1/4] | ⚪ | Path normalization in CommandShare is shallow. Relative inputs such as `./x` or `a/../x` are not normalized before the anchored attribute line is built. They fall through to the post-write `check_attr_filter` conflict and rollback path rather than a clean pre-mutation refusal. An absolute path under a symlinked root, such as /var versus /private/var, fails `relative_to` and surfaces as "resolves outside" instead. | src/tools/dot/commands/localize/share.py:86 | 3 | BLAKE |
| R21 | [1/4] | ⚪ | Documentation claims status is clean immediately after sharing, although sharing deliberately stages the target and `.gitattributes`. State that status becomes clean after committing those changes. | docs/source/tools/dot.rst:350 | 6 | BOB |

Consolidation note: row R1 merged citations differing only by line suffix (`__init__.py:3` ~ `__init__.py:4`).

### Decision-gate merges (judgment call on issue text plus file)

`consolidate_findings.py` left several rows split because the reviewers cited the same defect at different line numbers. The decision gate treats each group below as one finding with the combined finder list, so none of them is single-voiced away:

- R7 + R12 — leading-dash path unreachable through `CommandShare` (`ls_files` missing `--`) — ALICE, BOB
- R8 + R16 + R17 — `_index_mode` duplicates `capture_index_entry`'s git call and stage-0 parser — ALICE, BOB, CARL
- R13 + R19 — the attribute-quoting check rejects only space and tab, not `\n`/`\r` — ALICE, BOB
- R14 + R20 — relative input spelling is not normalized before the anchored attribute line — BLAKE, BOB
- R2 + R18 — `resolve_home` does not strip a trailing separator on a Windows-spelled home — ALICE, BLAKE, CARL

### Decision-gate dispositions

- Fixed this cycle: R1, R2, R3, R5, R6, R7, R8, R12, R13, R14, R16, R17, R18, R19, R20.
- Deferred to batch end: R4 (requirements ambiguity — the PRD pins `dot filter clean %f` verbatim, while the code's `-- %f` is the guard the PRD's own shell-unsafe-path requirement needs; a human decides whether to keep `--` and amend the PRD).
- Discarded as single-voice Medium/Low: R9, R10, R11, R15, R21.

## Alice

Consensus lens, implementation-aware. Five findings (R1, R2, R7, R8, R19 above).

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

R9 fail: the PRD's shell-unsafe-path requirement is not reachable through `CommandShare`.

## Blake

Blind lens, PRD-only. Six findings (R3, R4, R9, R10, R2, R20 above).

Verified OK by Blake:
- The narrow run of the five new test files passed (281 passed). `hostfilter.py` implements the boundary regex, token refusal, Windows spellings and drive-letter-only case folding.
- The CLI has a hidden `filter` group with binary stdout/stderr writes, an R12 comment citing the discovery, and exit 1 on token refusal. `--shared` combined with `--to` is rejected before any mutation.
- The real-Git tests cover index tokens, checkout, setup self-heal, two-host pull, anchored attributes, missing dot, divergence patch and reverse hunk.
- Docs, README, AGENTS.md (the "dot filter" line appears once) and CHANGELOG exist, and the doc assertion script prints ok.

B1: fail
B2: fail
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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens (codex, static sandbox). Ten findings (R5, R6, R11, R12, R13, R14, R15, R16, R21 above).

FIX: ten items, all listed in the consolidated table.
VERIFY: (none)
KNOWN: (none)

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: fail
R8: fail
R9: fail
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

UI/design lens (gemini via copilot backend). Three findings (R17, R18, and a duplicate of R1).

Carl independently ran `sphinx-build` (clean), `mypy src/lib/ src/tools/` (clean) and `ruff check src/tools/dot/ tests/tools/dot/` (clean), and reproduced the known `test_pull_divergence_two_hosts.py` global-gpgsign flake.

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

Verdict: 21 findings
Tests: 5568 passed, 3 failed, 16 skipped, 1 xfailed (suite run this cycle; the 3 failures are documented pre-existing environment noise outside this PRD - 2 klyreon identity tests from an exported GIT_AUTHOR_NAME, 1 postup collect test that calls real gh)
