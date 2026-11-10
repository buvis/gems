---
design: skip
default_model: sonnet
model_tier_rationale: exact paths, names and messages given; the risk is rewriting the existing `.local.yaml` tests, pinned by rg premises in the tasks
---

# Configuration: machine-local layer in ~/.local/.config/buvis

Source: GitHub issue buvis/gems#273 and the owner decisions in its comment (2026-11-10).

## Overview

### Problem Statement

`ConfigurationLoader` looks for a machine-local twin (`config.local.yaml`, `buvis.local.yaml`, `buvis-<tool>.local.yaml`) beside each shared file in `~/.config/buvis/` (`_get_candidate_files` and `find_config_files_ranked` in `src/lib/buvis/pybase/configuration/loader.py`). The dotfiles convention puts machine-local config under `~/.local/` at the mirrored path and leaves nothing loose beside tracked config: `~/.config/buvis/` is tracked in the dotfiles repo, and only `~/.local` travels to a new machine. A loose `*.local.yaml` in `~/.config/buvis` is easy to forget and is lost on a move.

Owner decisions (issue comment, 2026-11-10):

- Drop the sibling twins in this release, with no deprecation period. The loader stops reading `config.local.yaml`, `buvis.local.yaml` and `buvis-<tool>.local.yaml`. The machine-local layer is `~/.local/.config/buvis/` only, with the plain names (`config.yaml`, `buvis.yaml`, `buvis-<tool>.yaml`).
- Breaking change: list it under **Removed** in the changelog and say where to move the files.
- Update every text that names the twins: the `sysup` CLI message, `docs/source/configuration.rst`, `docs/source/tools/sysup.rst`, `docs/source/tools/backup.rst`.
- Check the `dot` tool and its host-links manifest for special handling of `*.local.yaml` names.

### Target Users

The owner, running gems tools on several machines with `~/.config/buvis/` tracked in dotfiles and `~/.local/` backed up per machine. The braid PRD 00123 depends on this layer for machine-only skill sources.

### Success Metrics

- `uv run pytest tests/lib/pybase/configuration/test_loader.py -k "machine_local"` passes, including `test_machine_local_dir_overrides_shared_tool_key`.
- `rg -n "\.local\.yaml" src/lib src/tools docs/source` prints nothing.
- Full gate green at the end: `uv run pytest`, `uv run mypy src/lib/ src/tools/`, `uv run sphinx-build -b html docs/source docs/build/html`.

## Functional Decomposition

### Capability: Machine-local config layer

Read machine-local config from `~/.local/.config/buvis/` and stop reading sibling twins.

#### Feature: Machine-local search directory

- **Description**: Add `~/.local/.config/buvis` to the config search path, above `~/.config/buvis` and below `$BUVIS_CONFIG_DIR`.
- **Inputs**: `Path.home()`, `$BUVIS_CONFIG_DIR`, the `config_dir` override.
- **Outputs**: `get_config_dirs()` returns, highest first: `$BUVIS_CONFIG_DIR` (when set and non-empty), `Path.home() / ".local" / ".config" / "buvis"`, `Path.home() / ".config" / "buvis"`. `ConfigurationLoader._get_search_paths(config_dir)` returns `[Path(config_dir).expanduser(), Path.home() / ".local" / ".config" / "buvis", Path.home() / ".config" / "buvis", Path.cwd()]` when `config_dir` is given, else `[*get_config_dirs(), Path.cwd()]`.
- **Behavior**: Precedence, lowest first: cwd < `~/.config/buvis` < `~/.local/.config/buvis` < `$BUVIS_CONFIG_DIR`. Because `get_config_dirs()` gains the directory, the zettel template loader and query spec parser (both iterate `get_config_dirs()`) also see machine-local templates and queries. A missing directory is skipped like any other missing directory. The existing `_is_safe_path` check (the candidate's resolved path must sit under one of the search paths) and the world-writable warning in `load_yaml` apply to files in the new directory with no new code: the directory is one of `paths`.

#### Feature: Drop sibling twins

- **Description**: Stop reading `*.local.yaml` beside the shared files.
- **Inputs**: Search paths, tool name.
- **Outputs**: `_get_candidate_files(paths, tool)` returns, per base, `config.yaml`, `buvis.yaml`, `buvis-{tool}.yaml` (the last only for a non-empty tool name). `find_config_files_ranked` ranks the same three stems per directory.
- **Behavior**: A `buvis-sysup.local.yaml` in any search directory is ignored. No warning is logged for it (owner chose no deprecation period).

### Capability: Text that names the twins

Every user-facing string and doc that names `*.local.yaml` points at the new layer instead.

#### Feature: sysup disabled-item message

- **Description**: `sysup refresh` on a disabled item names the new file.
- **Inputs**: Disabled expiry item name.
- **Outputs**: `item '<item>' is disabled; enable it in ~/.local/.config/buvis/buvis-sysup.yaml first`.
- **Behavior**: Same panic as today (`src/tools/sysup/cli.py:251`), new text only.

#### Feature: Docs and comments

- **Description**: Configuration, sysup and backup docs and the sysup bundled default describe the new layer.
- **Inputs**: Current text.
- **Outputs**: Updated text, no `.local.yaml` left.
- **Behavior**: `docs/source/configuration.rst` lists the real discovery order in "File Locations" (lines 316-323) and "YAML Not Loading" (lines 713-718): `$BUVIS_CONFIG_DIR`, `~/.local/.config/buvis`, `~/.config/buvis`, current directory, and drops the `$XDG_CONFIG_HOME` and `~/.buvis` entries the code never read. The layer-3 comment at line 392 reads `# layer 3 — machine-local (~/.local/.config/buvis), higher still: ADD one, CANCEL a default`. `docs/source/tools/sysup.rst` "Sharing across machines" (lines 174-194) says: put a one-machine value in `~/.local/.config/buvis/buvis-sysup.yaml`; it overrides `~/.config/buvis/buvis-sysup.yaml` per key; `~/.local` is outside the dotfiles repo and is backed up with the machine. Lines 298, 335, 358 and 363 name `~/.local/.config/buvis/buvis-sysup.yaml`. `docs/source/tools/backup.rst:173` names `~/.local/.config/buvis/buvis-backup.yaml`. `src/tools/sysup/default.yaml` lines 5 and 141 name `~/.local/.config/buvis/buvis-sysup.yaml`.

#### Feature: Changelog

- **Description**: Record the breaking removal.
- **Inputs**: None.
- **Outputs**: Under `## [Unreleased]`, a `### Removed` entry: `- **configuration**: the loader no longer reads machine-local twins (`config.local.yaml`, `buvis.local.yaml`, `buvis-<tool>.local.yaml`) beside shared files; move each to `~/.local/.config/buvis/` under its plain name (`buvis-<tool>.local.yaml` becomes `~/.local/.config/buvis/buvis-<tool>.yaml`)`, and an `### Added` entry: `- **configuration**: machine-local config layer in `~/.local/.config/buvis/`, above `~/.config/buvis/` and below `$BUVIS_CONFIG_DIR``.
- **Behavior**: One commit carries the code and both entries.

### Capability: dot check

#### Feature: No special `*.local.yaml` handling in dot

- **Description**: Confirm dot and its host-links code treat `*.local.yaml` like any other name.
- **Inputs**: `src/tools/dot/`.
- **Outputs**: No code change when the premise holds.
- **Behavior**: Premise: `rg -n "local\.yaml|\.local\." src/tools/dot` prints nothing (checked 2026-11-10; dot's only "local" handling is `dot localize`, whose default source `.local/<path>` already matches the new layout). The task re-runs the search; on a hit, it stops and records the hit in the PRD's review notes instead of changing dot.

## Structural Decomposition

### Repository Structure

```text
src/lib/buvis/pybase/configuration/loader.py     # search dirs, candidate stems
src/tools/sysup/cli.py                           # disabled-item message
src/tools/sysup/default.yaml                     # comments naming the layer
docs/source/configuration.rst                    # discovery order, layer-3 comment
docs/source/tools/sysup.rst                      # sharing-across-machines text
docs/source/tools/backup.rst                     # machine-local example header
CHANGELOG.md                                     # Removed + Added entries
tests/lib/pybase/configuration/test_loader.py    # loader tests
tests/lib/pybase/configuration/test_paths.py     # get_config_dirs tests
tests/tools/sysup/test_sysup_cli.py              # disabled-item message test
tests/tools/sysup/test_config.py                 # local-layer fixture names
```

### Module: Configuration loader

- **Location**: `src/lib/buvis/pybase/configuration/loader.py`
- **Maps to capability**: Machine-local config layer
- **Responsibility**: Discover config files in precedence order.
- **Exports**:
  - `get_config_dirs()` - config dirs, highest first, now including `~/.local/.config/buvis`
  - `ConfigurationLoader._get_search_paths()` - search dirs plus cwd
  - `ConfigurationLoader._get_candidate_files()` - three stems per dir
  - `ConfigurationLoader.find_config_files_ranked()` - low-to-high ranked files
- New symbols: `test_machine_local_dir_overrides_shared_tool_key`, `test_machine_local_dir_ranks_between_shared_and_buvis_config_dir`, `test_sibling_local_twin_is_ignored`, `test_machine_local_symlink_outside_search_paths_is_skipped`

### Module: sysup CLI and default

- **Location**: `src/tools/sysup/cli.py`, `src/tools/sysup/default.yaml`
- **Maps to capability**: Text that names the twins
- **Responsibility**: User-facing message and bundled-config comments.
- **Exports**: none new.

### Module: Docs and changelog

- **Location**: `docs/source/configuration.rst`, `docs/source/tools/sysup.rst`, `docs/source/tools/backup.rst`, `CHANGELOG.md`
- **Maps to capability**: Text that names the twins
- **Responsibility**: Describe the layer and the breaking change.
- **Exports**: none.

## Dependency Graph

### Foundation Layer (Phase 0)

No dependencies - built first.

- **Configuration loader**: the new search directory and the three-stem candidate list.

### Core Layer (Phase 1)

- **sysup CLI and default**: Depends on [Configuration loader] (the message names the layer the loader reads).

### Integration Layer (Phase 2)

- **Docs and changelog**: Depends on [Configuration loader, sysup CLI and default].

## Implementation Phases

### Phase 0: Foundation

**Goal**: The loader reads `~/.local/.config/buvis` and no longer reads twins.

**Tasks**:

- [ ] In `src/lib/buvis/pybase/configuration/loader.py`, make `get_config_dirs()` return `$BUVIS_CONFIG_DIR` (if set), then `Path.home() / ".local" / ".config" / "buvis"`, then `Path.home() / ".config" / "buvis"`; make the `config_dir` branch of `_get_search_paths` return `[Path(config_dir).expanduser(), Path.home() / ".local" / ".config" / "buvis", Path.home() / ".config" / "buvis"]` before cwd is appended; update both docstrings to the new order (no deps) - Acceptance: in `tests/lib/pybase/configuration/test_paths.py`, `test_default_without_env` asserts the two-dir list and `test_with_buvis_config_dir` the three-dir list, both with the new entry; `TestGetSearchPaths` in `tests/lib/pybase/configuration/test_loader.py` asserts the new order; `uv run pytest tests/lib/pybase/configuration/test_paths.py tests/lib/pybase/configuration/test_loader.py -k "GetConfigDirs or GetSearchPaths"` passes.
- [ ] Remove the twin from `_get_candidate_files` (delete the `.local.yaml` append) and from `find_config_files_ranked` (use `base_stems` directly, delete the interleave and its comment); rewrite both docstrings to the three-stem order. Premise: `rg -c "local" tests/lib/pybase/configuration/test_loader.py` prints 39 before the edit; if not, re-read the tests before rewriting them. Rewrite the twin tests: replace `test_local_twin_overrides_shared_and_adds_keys`, `test_local_twin_ordered_immediately_above_shared` and `test_no_local_file_is_backward_compatible` with `test_machine_local_dir_overrides_shared_tool_key` (a `~/.local/.config/buvis/buvis-sysup.yaml` value overrides the same key in `~/.config/buvis/buvis-sysup.yaml` and adds a machine-only key, through `find_config_files_ranked` + `merge_configs`, with `HOME` set to `tmp_path`), `test_machine_local_dir_ranks_between_shared_and_buvis_config_dir`, and `test_sibling_local_twin_is_ignored` (a `buvis-sysup.local.yaml` beside `buvis-sysup.yaml` is not returned); drop the `.local.yaml` entries from the expected lists in `TestGetCandidateFiles` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_loader.py` passes; `test_sibling_local_twin_is_ignored` fails against the old loader.
- [ ] Add `test_machine_local_symlink_outside_search_paths_is_skipped` to `TestFindConfigFilesLogging`: a `~/.local/.config/buvis/buvis.yaml` symlink to a file outside every search path is skipped and logged as unsafe (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_loader.py -k machine_local` passes.

**Exit Criteria**: `uv run pytest tests/lib/pybase/configuration` passes.

### Phase 1: Core

**Goal**: sysup names the new file.

**Tasks**:

- [ ] Change the `is disabled` panic in `src/tools/sysup/cli.py` to `f"item '{item}' is disabled; enable it in ~/.local/.config/buvis/buvis-sysup.yaml first"`; tighten the `"is disabled" in result.output` assertion in `tests/tools/sysup/test_sysup_cli.py` to the full new text; in `tests/tools/sysup/test_config.py` `test_ntfy_local_layer_merges_over_shared_config`, rename the machine file to `tmp_path / "local" / "buvis-sysup.yaml"` (create the dir); change the comments at `src/tools/sysup/default.yaml` lines 5 and 141 to name `~/.local/.config/buvis/buvis-sysup.yaml` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/sysup/test_sysup_cli.py tests/tools/sysup/test_config.py` passes; `rg -n "local\.yaml" src/tools/sysup tests/tools/sysup` prints nothing.
- [ ] Re-check the dot premise: run `rg -n "local\.yaml|\.local\." src/tools/dot` (depends on: Phase 0) - Acceptance: the search prints nothing and dot is unchanged; on a hit, stop, change nothing in dot, and record the hit in the review notes.

**Exit Criteria**: No `.local.yaml` text left in `src/`.

### Phase 2: Integration

**Goal**: Docs and changelog describe the layer and the removal.

**Tasks**:

- [ ] Rewrite `docs/source/configuration.rst` "File Locations" and "YAML Not Loading" lists and the layer-3 comment at line 392 as given in the Docs and comments feature; rewrite `docs/source/tools/sysup.rst` lines 174-194, 298, 335, 358, 363 and `docs/source/tools/backup.rst:173` the same way (depends on: Phase 1) - Acceptance: `rg -n "\.local\.yaml" docs/source` prints nothing; `rg -n "\.local/\.config/buvis" docs/source/configuration.rst docs/source/tools/sysup.rst docs/source/tools/backup.rst` hits all three files.
- [ ] Add the `### Removed` and `### Added` entries under `## [Unreleased]` in `CHANGELOG.md`, text as given in the Changelog feature (depends on: Phase 1) - Acceptance: `rg -n "~/.local/.config/buvis" CHANGELOG.md` prints both entries.

**Exit Criteria**: `uv run pytest`, `uv run mypy src/lib/ src/tools/`, and `uv run sphinx-build -b html docs/source docs/build/html` pass; `rg -n "\.local\.yaml" src/lib src/tools docs/source` prints nothing.

## Test Strategy

### Critical Scenarios

- **Happy path**: `~/.local/.config/buvis/buvis-sysup.yaml` sets `x: machine`, `~/.config/buvis/buvis-sysup.yaml` sets `x: shared` → Expected: merged `x == "machine"`.
- **Edge case**: `$BUVIS_CONFIG_DIR/buvis-sysup.yaml` also sets `x: env-dir` → Expected: `x == "env-dir"`.
- **Edge case**: only a sibling `~/.config/buvis/buvis-sysup.local.yaml` exists → Expected: it is not loaded.
- **Error case**: a symlink in `~/.local/.config/buvis` points outside all search paths → Expected: skipped, warning logged.

## Risks

- **Silent loss of machine values after upgrade**: a twin left in place is ignored with no warning (owner's choice). Mitigation: the changelog entry names the move. Outside gems, the main machine moves the plaintext of the git-secret file `buvis-mcp-calcard.local.yaml` to `~/.local/.config/buvis/buvis-mcp-calcard.yaml` right after upgrading and stops tracking it in dotfiles; this is a machine step, not a task here.
- **Wider reach through `get_config_dirs()`**: zettel templates and query specs now also load from `~/.local/.config/buvis`. That matches the layer's intent and a missing dir costs nothing.
