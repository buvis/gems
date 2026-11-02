---
prd: docs/dev/project-management/prds/wip/00109-backup-bundle-items-and-skip-outcomes-v1.md
review: 1
date: 2026-11-02
head_sha: 7f4b462f1275c9306d7cc452cb2024a429f2c371
reviewers: alice,blake,bob,eve
agents:
  alice: available
  blake: available
  bob: available
  carl: disabled
  eve: available
---

# Review: 00109-backup-bundle-items-and-skip-outcomes-v1

Diff range: `5a3ab34deb025e2a4223f9af876ec0256c2de177..7f4b462f1275c9306d7cc452cb2024a429f2c371`

codex_rung_guard: fired (1 codex-implemented task(s))

Attended recovery review (handoff `autopilot/reports/202610292344-review-20261102-handoff.md`). Completion review never ran for this held fast-track PRD. State restored from `autopilot/reports/00109-backup-bundle-items-and-skip-outcomes-v1-build-state.json`; work base and task provenance unchanged.

Reviewed tree: detached worktree at the PRD's build end `7f4b462f` (`~/git/src/worktrees/gems/review-00109`). The staged diff was path-scoped to `src/`, `tests/`, `docs/source/`, `CHANGELOG.md` and `README.md`, as for 00107. Staged with `autopilot review-stage` in standalone mode. The full isolated suite ran at `7f4b462f` this cycle.

Provider diversity: the build ran on OpenAI gpt-6.1-sol via codex. Alice, Blake and Eve ran as native Anthropic subagents; Bob ran on codex with the inlined prompt.

Carl: disabled (no UI surface; batch report records his nested-dispatch guard failure). Pack: failed (worktree not a registered repo); prompts carry `(no pack available this cycle)`.

Fail-first replay: the tool skipped it (no pytest in its temporary venv). Re-run by hand: the three new test files from `7f4b462f` copied onto the pre-PRD base `5a3ab34d` (the review-00107 worktree and its venv): 56 selected, 56 failed. No `[MECH]` tautological-shape lines.

Consolidation: script output corrected model-side. Merged two paraphrase pairs the script kept apart: the `items` null or non-list message (Alice, Blake, Eve) and the missing fail-first evidence (Alice, Eve). Eve's first output had no issue lines; one format retry. Bob's issue lines carry a leading `- ` but parsed.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟠 | An inaccessible item can become a successful skip: `os.path.lexists()` returns false for permission errors, so an unreadable parent directory is reported as missing. Existing tests inject errors only after presence succeeds. Distinguish absence from access errors and add an inaccessible-parent test. | src/tools/backup/capabilities/tar_archive.py:230 | 1 | BOB |
| R2 | [1/4] | 🟠 | Permission-denied `source` is a silent successful skip ("source not found") on Python 3.14 (`Path.is_dir()`/`exists()` return False under EACCES, probed) but a failed step on 3.11-3.13 (PermissionError propagates to the Runner); CI runs all four, and an unreadable source exits 0 on 3.14 | src/tools/backup/capabilities/tar_archive.py:106 | 1 | EVE |
| R3 | [1/4] | 🟠 | A bundle whose `out` lies under `source` but under no selected item is rejected by the unconditional containment check, blocking the PRD's headline case (`source: ~`, items `.gitconfig`/`.npmrc`, `out` under the default `~/.local/backup`) | src/tools/backup/capabilities/tar_archive.py:112 | 1 | EVE |
| R4 | [3/4] | 🟡 | `items` given as a non-list (a bare YAML string `items: .gitconfig`, or `items:` null) goes through `_as_str_tuple`, becomes `()`, and fails with the misleading "items must not be empty". `bundle = "items" in kwargs` also treats an explicit null as an empty bundle rather than "omitted". Consider a specific "items must be a list of strings" message | src/tools/backup/capabilities/tar_archive.py:119 | 1 | ALICE, BLAKE, EVE |
| R5 | [2/4] | 🟡 | `_normalize_items` rejects any item whose first component merely starts with `..`, so a valid literal filename such as `..hidden` or `..foo/bar` fails with "must be a relative path inside the source". The check should be `relative.parts[0] == ".."` | src/tools/backup/capabilities/tar_archive.py:209 | 1 | ALICE, EVE |
| R6 | [2/4] | 🟡 | On the skip path for "all items absent or excluded", the message "no selected items to archive" names neither source, out, nor label, so the warning cannot be attributed in a multi-instance run | src/tools/backup/capabilities/tar_archive.py:128 | 1 | BLAKE, EVE |
| R7 | [2/4] | 🟡 | PRD says `WalkResult` gains `missing`. The implementation instead returns `tuple[WalkResult, list[str]]` from `_select_items` and threads `missing` as a separate local in `run`. Either add `missing` to `WalkResult` per the PRD or record the deviation | src/tools/backup/capabilities/tar_archive.py:220 | 1 | ALICE, BLAKE |
| R8 | [2/4] | 🟡 | TarArchive.run grew from about 49 to 67 lines (mechanical facts block, tar_archive.py:76), over the 50-line limit. Extract the bundle branch into a helper | src/tools/backup/capabilities/tar_archive.py:76 | 1 | ALICE, BOB |
| R9 | [2/4] | 🟡 | No fail-first evidence for any new test: the mechanical replay died before running, so the new test files have not been shown to fail against base 5a3ab34d | N/A | 1 | EVE, ALICE |
| R10 | [1/4] | 🟡 | Spec exports `StepResult(label, success, message="", archive=None, skipped=False)`, so `skipped` can be passed positionally. The implementation makes `skipped` keyword-only (`*, skipped`), so a fifth positional argument raises TypeError. | src/tools/backup/step_result.py:29 | 1 | BLAKE |
| R11 | [1/4] | 🟡 | The YAML example uses unquoted `source: ~`, which YAML parses as null, leaving no source configured. Quote it as `source: "~"`. | docs/source/tools/backup.rst:91 | 1 | BOB |
| R12 | [1/4] | 🟡 | `test_no_selected_members_skips_and_preserves_existing_output` asserts only that `result.message` is truthy; the PRD's "; missing items: a, b" tail on the all-absent skip is unpinned and the excluded case is not shown tail-free | tests/tools/backup/test_skip_outcomes.py:999 | 1 | EVE |
| R13 | [1/4] | ⚪ | `_walk_tree` gained a `root` parameter, but its docstring does not say that exclude paths are relative to `root` rather than `source` | src/tools/backup/capabilities/tar_archive.py:260 | 1 | ALICE |
| R14 | [1/4] | ⚪ | The spec says to normalize with `posixpath.normpath`. The code uses `os.path.normpath`, which is identical on POSIX but differs on Windows. | src/tools/backup/capabilities/tar_archive.py:208 | 1 | BLAKE |
| R15 | [1/4] | ⚪ | A present non-regular item (fifo, socket, device) is silently ignored, neither archived nor reported. If it is the only item, the step becomes a skip. | src/tools/backup/capabilities/tar_archive.py:249 | 1 | BLAKE |
| R16 | [1/4] | ⚪ | Unrelated churn: the two `no source configured` / `no out path configured` branches were collapsed into one conditional-message block that no PRD task touches | src/tools/backup/capabilities/tar_archive.py:84 | 1 | EVE |
| R17 | [1/4] | ⚪ | `TestSkippedArchives` is parametrized over `engine` although every path under test returns before the engine is consulted (16 tests for 8 behaviours) | tests/tools/backup/test_skip_outcomes.py:927 | 1 | EVE |
| R18 | [1/4] | ⚪ | `TestStepResult` is parametrized over two `(label, message)` string pairs that exercise no different behaviour | tests/tools/backup/test_skip_outcomes.py:912 | 1 | EVE |
| R19 | [1/4] | ⚪ | Dead test scaffolding: the `denied_stat`/`os.stat` patch can never fire (`path.lstat()` raises first) and `monkeypatch.chdir(other)` has no assertion depending on cwd | tests/tools/backup/test_bundle_items.py:762 | 1 | EVE |

## Alice

Five findings at medium or low (R4, R5, R7, R8, R9 and R13). R12: fail; other R lines pass.

## Blake

Six findings (R4, R6, R7, R10, R14, R15). B2: fail, B3: fail; other B lines pass.

## Bob

Three findings (R1, R8, R11). Consensus rubric: R1, R9, R10, R12 fail.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Eve

Eleven issue lines after one format retry (R2, R3, R4, R5, R6, R9, R12, R16 to R19). Re-ran `pytest tests/tools/backup` (210 passed), ruff and mypy clean; two EACCES probes on 3.13.18 and 3.14.10 back R2.

KNOWN: `_select_items` re-implements ancestor `.bkpignore` layering instead of calling `resolve_state_for_path`; the same EACCES class exists in untouched `_walk_tree` lines; an item dropped by exclude rules is reported nowhere. All pre-existing or out of PRD scope.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Decision gate

Each HIGH was checked against the PRD and HEAD before classification.

- R1 and R2 are confirmed. PRD "Reading failures (permission denied, file vanishing after selection) fail the step, never count as missing." Both defects survive at HEAD (`tar_archive.py` `_select_items` uses bare `lexists`; `run` and `plan` use `is_dir`/`exists`). Fix in rework.
- R3 is deferred as a requirements question. The out-inside-source guard predates this PRD, the PRD does not specify it for bundles, and the PRD 00110 plan contract restates it unconditionally. Relaxing it is a new decision.
- R4, R5 and R6 are fixed in rework (two or more finders each; all present at HEAD).
- R7 is deferred: a structural deviation from the PRD export list with equivalent behavior.
- R8 is discarded: resolved at HEAD, where `TarArchive.run` is 30 lines after `de84f6f1` split it.
- R9 is discarded: refuted by the manual replay above (56 of 56 fail at base).
- R10 to R19 are single-voice medium or low: discarded into the ledger.

Verdict: 19 findings

Tests: 5825 passed, 0 failed, 16 skipped (suite run this cycle)
