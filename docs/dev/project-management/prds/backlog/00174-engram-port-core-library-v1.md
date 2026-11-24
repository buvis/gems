---
default_model: opus
model_tier_rationale: equivalence obligation - ported code must keep standalone Engram behavior, chunk cache keys and DB bytes identical
---

# Engram port Phase 1: core library

Source: `docs/dev/project-management/discovery/00161-engram-port-plan.md` (Phase 1) and `docs/dev/project-management/discovery/00161-engram-qa-handoff.md`.
Source commit: buvis/engram e413696 (master; PRDs 00014-00016 done; last code change d366537). At that commit the main suite gave 1402 passed and the eval suite 53 passed, in the checkout venv and in a venv built from `uv.lock` (2026-11-24).

## Overview

### Problem Statement

Engram runs as a standalone `uv tool install .` from its own repo. The user decided on 2026-11-16 to ship it inside buvis-gems. Phase 1 moves the Engram library and its tests into `src/tools/engram` with no change in behavior. Later phases add settings (2), the Click CLI (3), and the release and cutover (4). Until Phase 4, the installed standalone `engram` stays the only executable. A Gems release before then must not take `~/.local/bin/engram`.

### Target Users

The user and the agent hosts that call `engram` (autopilot catchup and review stage, the agent-plugins engram plugin, git-ferry catchup). Phase 1 changes nothing they see. The later phases and held QA PRDs 00163-00173 need this code to land first.

### Success Metrics

- `uv run pytest tests/tools/engram` passes. It holds every source test file except `tests/test_harness.py`.
- `uv run mypy src/lib/ src/tools/` and `uv run ruff check src/ tests/` pass with the ported code.
- `uv run --isolated --python 3.11 --all-extras --group test pytest tests/tools/engram` passes, so the 3.11 floor is checked locally.
- After the branch reaches `master`, the Gems CI `lint`, `lib` and `tools` jobs pass on every ubuntu and macOS cell for Python 3.11-3.15. `test.yml` runs only on pushes and pull requests to `master`, so this is the port plan's gate for starting Phase 2, not a task in this PRD.
- `pyproject.toml` has no `engram` key in `[project.scripts]`.

## Functional Decomposition

### Capability: Library port

Port the Engram product modules from e413696 into the Gems tool package `engram`. The import name stays `engram`, so `from engram.store import ...` stays valid.

#### Feature: Module port

- **Description**: Copy every module in source `src/engram/` except `harness.py` to `src/tools/engram/`, with the same file names.
- **Inputs**: Source files at e413696: `__init__.py`, `chunker.py`, `cli.py`, `client.py`, `corpora.py`, `diffmap.py`, `findings.py`, `harvest.py`, `indexer.py`, `mcp_server.py`, `memory.py`, `migrate.py`, `nudge.py`, `pack.py`, `query.py`, `store.py`, `symbols.py`, `transcripts.py`.
- **Outputs**: The same 18 modules in `src/tools/engram/`. No `__main__.py`: nothing runs `python -m engram` before Phase 3.
- **Behavior**: Make only the edits that Gems ruff, mypy strict and Python 3.11 need (annotations, `cast`, import order). Do not add lint-suppression comments. Do not change any string, output format, exit code, SQL, chunking rule, cache key or default path. `cli.py` keeps its argparse `main(argv)` as an internal module. No console script points to it until the Phase 4 PRD. Phase 3 replaces it with Click. `harness.py` is not ported (port plan: redesign as `engram bench` in Phase 5). `config.toml` reading stays as it is until Phase 2.

#### Feature: Windows-safe write lock

- **Description**: `store.write_lock` keeps `fcntl.flock(fd, LOCK_EX | LOCK_NB)` on POSIX and uses msvcrt.locking(fd, msvcrt.LK_NBLCK, 1) on Windows. msvcrt is the Windows-only stdlib module, so it does not resolve on this machine.
- **Inputs**: `lock_path`.
- **Outputs**: The same context manager. Contention raises `StoreBusyError` with the unchanged message `engram store busy: {lock_path} is held by another harvest or rebuild`.
- **Behavior**: Select the branch with `sys.platform == "win32"`. Put the Windows call in `_lock_nonblocking_windows(fd)`. It gets the msvcrt module through `importlib.import_module("msvcrt")` and maps `OSError` to `StoreBusyError`, so a test can run it on POSIX with a fake msvcrt module in `sys.modules`. The POSIX path stays byte-for-byte the source code, because `tests/test_write_lock.py` pins `fcntl.flock`.

### Capability: Test port

#### Feature: Main suite port

- **Description**: Copy the source `tests/` tree, except `tests/test_harness.py`, to `tests/tools/engram/`.
- **Inputs**: 42 test files, the helpers `_cli_helpers.py`, `_embedding_server.py`, `_migrate_helpers.py` and `_pack_helpers.py`, and the two files in `tests/fixtures/`.
- **Outputs**: 1356 collected tests in `tests/tools/engram/`. This is the source count at e413696 without `test_harness.py`.
- **Behavior**: Change the helper imports, from `from _cli_helpers import` to `from tests.tools.engram._cli_helpers import`, and the same for the other three helpers. Gems runs pytest with `--import-mode=importlib`. Other edits are only those that `ruff check --fix` and `ruff format` make. Do not change, add or remove any assertion. No `__init__.py`: `tests/tools/braid` imports `tests.tools.braid.helpers` the same way without one. The `private` marker leaves with `test_harness.py`, because its only use is there. The gold-source data in `~/.local/share/engram/eval/` stays on disk and untouched.

### Capability: Packaging and repo wiring

#### Feature: `engram` extra

- **Description**: Add the extra `engram = ["sqlite-vec==0.1.9", "tree-sitter==0.26.1", "tree-sitter-language-pack==1.25.2"]`, and add `engram` to the `all` extra.
- **Inputs**: Source `uv.lock` at e413696. It resolves sqlite-vec 0.1.9, tree-sitter 0.26.1 and tree-sitter-language-pack 1.25.2.
- **Outputs**: `pyproject.toml` and `uv.lock` updated. The package `src/tools/engram` goes in the hatch wheel list. The marker `engram: engram tests` goes in the pytest markers. A mypy override with `ignore_missing_imports` covers `sqlite_vec` and `tree_sitter_language_pack`.
- **Behavior**: Use exact pins, because an unpinned `tree-sitter` resolves to 0.27.0. The source never tested 0.27.0, and chunk output decides the production cache keys. Moving to 0.27.0 needs its own PRD with a chunk-equality check.

#### Feature: Deferred console script

- **Description**: `tools/lib/check_tool_wiring.py` gets an explicit map of tools whose console script is deferred: `{"engram": "PRD 00174: script lands with the Engram cutover release (port Phase 4)"}`.
- **Inputs**: The map entry.
- **Outputs**: `check()` reports no missing-script error for `engram`. It still reports a missing hatch package for it, and it still checks scripts for every other tool.
- **Behavior**: Premise: a script entry would put an `engram` executable in every buvis-gems install. That includes sysup's `uv tool upgrade --all`, which would collide with the standalone tool that owns `~/.local/bin/engram`. The Phase 4 PRD removes the entry and adds the script.

#### Feature: Repo documentation

- **Description**: Update `AGENTS.md`: add `engram/` to the architecture tree, add `engram` to the extras list, and add one sanctioned console exception.
- **Inputs**: Port plan contract items 3-5 and 7.
- **Outputs**: An exception bullet: "Engram's machine-read surfaces (query, status, harvest, lookup, memory and pack stdout lines, nudge hook JSON, MCP stdio JSON-RPC, and the `not inside a registered repo` stderr line) keep the standalone byte-exact writes (port plan 00161 contract)."
- **Behavior**: Add one `CHANGELOG.md` entry under `[Unreleased]` / `### Added`, with this exact text: **engram**: engram extra with the ported Engram library; the engram command arrives with the cutover release.

## Structural Decomposition

### Repository Structure

```
src/tools/engram/              # Maps to: Library port
├── __init__.py
├── chunker.py
├── cli.py                     # internal argparse main(argv), replaced in Phase 3
├── client.py
├── corpora.py
├── diffmap.py
├── findings.py
├── harvest.py
├── indexer.py
├── mcp_server.py
├── memory.py
├── migrate.py
├── nudge.py
├── pack.py
├── query.py
├── store.py                   # Windows-safe write lock
├── symbols.py
└── transcripts.py
tests/tools/engram/            # Maps to: Test port (42 test files, 4 helpers, 2 fixtures, copied from source tests/)
├── _cli_helpers.py
├── _embedding_server.py
├── _migrate_helpers.py
├── _pack_helpers.py
├── fixtures/00001-engram-core-v1-review-5.md
├── fixtures/decision-audit.md
└── test_write_lock_windows.py # new: Windows lock branch with a fake msvcrt
                               # plus the 42 source test files listed below, names unchanged
tests/dev/test_check_tool_wiring.py
tools/lib/check_tool_wiring.py
pyproject.toml
uv.lock
AGENTS.md
CHANGELOG.md
```

The 42 test files, all under `tests/tools/engram/`: `test_backfill.py`, `test_backfill_empty_transition.py`, `test_backlog_delivery.py`, `test_chunker.py`, `test_cli.py`, `test_cli_embedding_errors.py`, `test_cli_index_rebuild.py`, `test_cli_index_status.py`, `test_cli_pack.py`, `test_cli_pack_diff.py`, `test_client.py`, `test_client_embed.py`, `test_corpora.py`, `test_diffmap.py`, `test_diffmap_decoding.py`, `test_empty_sources.py`, `test_findings.py`, `test_findings_store.py`, `test_followup_fixes.py`, `test_harvest.py`, `test_harvest_resolve.py`, `test_indexer.py`, `test_mcp_server.py`, `test_mcp_server_search.py`, `test_memory_attribution.py`, `test_memory_migrate.py`, `test_memory_migrate_symlinks.py`, `test_module_context.py`, `test_nudge.py`, `test_nudge_detection.py`, `test_pack.py`, `test_pack_correctness.py`, `test_pack_regressions.py`, `test_pack_worktree.py`, `test_query.py`, `test_read_repos_csv.py`, `test_repo_memory.py`, `test_smoke.py`, `test_store.py`, `test_symbols.py`, `test_transcripts.py`, `test_write_lock.py`.

### Module: engram library

- **Maps to capability**: Library port
- **Responsibility**: The Engram product code, ported unchanged in behavior.
- **Location**: `src/tools/engram/`
- **Exports**: The same public names as the source modules, for example `engram.store.open_store`, `engram.store.write_lock`, `engram.cli.main`.
- New symbols: `_lock_nonblocking_windows`

### Module: engram tests

- **Maps to capability**: Test port
- **Responsibility**: The source main suite, run by the Gems pytest config and CI.
- **Location**: `tests/tools/engram/`
- **Exports**: none (test code).
- New symbols: `tests/tools/engram/test_write_lock_windows.py`, `test_deferred_tool_needs_no_script`, `test_deferred_tool_still_needs_package`

### Module: wiring check

- **Maps to capability**: Packaging and repo wiring
- **Responsibility**: Let a tool defer its console script through an explicit, reasoned entry.
- **Location**: `tools/lib/check_tool_wiring.py`, `tests/dev/test_check_tool_wiring.py`
- **Exports**: `check()` (unchanged signature)
- New symbols: `DEFERRED_SCRIPTS`

### Module: packaging

- **Maps to capability**: Packaging and repo wiring
- **Responsibility**: The `engram` extra, wheel package entry, test marker, mypy override and lock.
- **Location**: `pyproject.toml`, `uv.lock`
- **Exports**: The `buvis-gems[engram]` extra.

### Module: repo documentation

- **Maps to capability**: Packaging and repo wiring
- **Responsibility**: Agent guidance and the user-visible change record.
- **Location**: `AGENTS.md`, `CHANGELOG.md`
- **Exports**: none.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **wiring check**: The deferred-script entry. Without it, the pre-commit hook rejects a new `src/tools/engram/__init__.py`.
- **packaging**: The `engram` extra, the hatch package, the marker, the mypy override and `uv.lock`.

### Core Layer (Phase 1)
- **engram library**: Depends on [packaging, wiring check].

### Integration Layer (Phase 2)
- **engram tests**: Depends on [engram library].
- **repo documentation**: Depends on [engram library].

External prerequisites: none. Source PRDs 00014-00016 are done at e413696. This PRD releases no held QA PRD. The QA release checkpoints run at Phase 3 and Phase 4 closeout, as the port plan requires.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Gems accepts an `engram` tool package with no console script.

**Tasks**:
- [ ] Add `DEFERRED_SCRIPTS` to `tools/lib/check_tool_wiring.py`, and skip the missing-script error for its keys only (no deps) - Acceptance: new tests in `tests/dev/test_check_tool_wiring.py` pass. `test_deferred_tool_needs_no_script` covers a deferred tool with no script entry, and `test_deferred_tool_still_needs_package` covers one with no package entry. All existing tests in that file still pass: `uv run pytest tests/dev/test_check_tool_wiring.py`.
- [ ] Wire packaging in `pyproject.toml`: the `engram` extra with the three exact pins, `engram` in `all`, `"src/tools/engram"` in the wheel packages, the `engram: engram tests` marker, and the mypy override. Then run `uv lock` (no deps) - Acceptance: `rg -n '^engram\s*=' pyproject.toml` matches only the extra line, never a `[project.scripts]` line. `uv lock --check` exits 0. With a requirements file that holds the three pins, `uv pip compile --only-binary :all: --python-platform x86_64-pc-windows-msvc --python-version 3.11 <file>` exits 0, and so does the same command with `--python-version 3.14`.

**Exit Criteria**: `python tools/lib/check_tool_wiring.py` exits 0 with `src/tools/engram/__init__.py` present.

### Phase 1: Core
**Goal**: The library is in Gems and passes lint and type checks.

**Tasks**:
- [ ] Copy the 18 source modules into `src/tools/engram/`, each from `git -C ~/git/src/github.com/buvis/engram show e413696:src/engram/<module>` (depends on: Phase 0) - Premise: the source code has not changed since e413696. Re-check at execution: `git -C ~/git/src/github.com/buvis/engram diff --quiet e413696 HEAD -- src tests` exits 0. If it fails, stop and report the changed files. Do not port a moved target. Acceptance: `uv run ruff check src/tools/engram` and `uv run mypy src/tools/engram` exit 0.
- [ ] Make `store.write_lock` Windows-safe as specified (depends on: copy task) - Acceptance: `uv run pytest tests/tools/engram/test_write_lock_windows.py` passes. It covers a fake msvcrt module that raises `OSError`, which gives `StoreBusyError` with the unchanged message, and a free lock, which yields and closes the fd.

**Exit Criteria**: `uv run ruff check src/` and `uv run mypy src/lib/ src/tools/` exit 0.

### Phase 2: Integration
**Goal**: The source suite runs green in Gems, and the repo docs match.

**Tasks**:
- [ ] Copy the tests, helpers and fixtures. Rewrite only the helper imports (depends on: Phase 1) - Acceptance: `uv run pytest tests/tools/engram --collect-only -q --ignore=tests/tools/engram/test_write_lock_windows.py` reports 1356 tests. `uv run pytest tests/tools/engram --cov=src/tools/engram --cov-fail-under=50` passes. For each of the 42 files, `rg -c '^\s*assert'` gives the same count in the source file at e413696 and in its port.
- [ ] Update `AGENTS.md` and `CHANGELOG.md` as specified (depends on: Phase 1) - Acceptance: `rg -n 'engram' AGENTS.md` shows the tree entry, the extras entry and the console exception. `rg -n '\*\*engram\*\*' CHANGELOG.md` matches under `[Unreleased]`.

**Exit Criteria**: The full local gate passes: `uv run pytest`, `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/lib/ src/tools/`, `uv run pytest tests/dev`, `python tools/lib/check_tool_wiring.py`, and `uv run --isolated --python 3.11 --all-extras --group test pytest tests/tools/engram`.

## Test Strategy

### Critical Scenarios
- **Happy path**: The ported suite runs under Gems config → Expected: the same 1356 tests pass as in the standalone at e413696.
- **Edge case**: Python 3.11 runs code written for 3.12 → Expected: the CI 3.11 cells pass. The source parses under 3.11 (checked 2026-11-24), so only runtime API gaps can fail.
- **Edge case**: Python 3.15 has no tree-sitter 0.26.1 wheel → Expected: CI builds it from the sdist on ubuntu and macOS. The 2026-11-24 locked venv did this on macOS.
- **Error case**: A Windows lock is held → Expected: `StoreBusyError` with the standalone message.
- **Error case**: A wiring check runs on a tool missing its package entry → Expected: still an error, even for a deferred tool.

## Risks

- **A Gems release before Phase 4 ships an `engram` script**: The deferred-script entry prevents it. The Phase 4 PRD must add the script and remove the entry together with the release and the install swap.
- **sqlite extension loading on CI interpreters**: `store.open_store` calls `enable_load_extension`. Source CI ran only ubuntu with uv-managed Python. If a Gems CI cell's interpreter lacks loadable-extension support, this PRD fails its exit criterion. Fix it with the CI job's Python provisioning (`uv python install` of the matrix version), not by skipping store tests.
- **Wheel floors**: tree-sitter-language-pack 1.25.2 publishes only macosx_15_0, manylinux_2_34 and win abi3 wheels. tree-sitter 0.26.1 has no cp315 wheels, so Windows on 3.15 needs a C build toolchain. Record any install failure. Do not loosen the pins in this PRD.
- **Parity drift during lint fixes**: A mypy or ruff fix that changes behavior breaks parity silently when no test covers it. Prefer annotations and `cast` over logic edits. The chunk and store tests guard the cache keys.
- **Held QA corrections**: PRDs 00163-00173 change behavior on purpose. Do not apply any of them here. This PRD ports the e413696 behavior only.
