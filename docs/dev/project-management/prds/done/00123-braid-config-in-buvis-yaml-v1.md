---
design: skip
default_model: sonnet
model_tier_rationale: field names, messages and request shape given; risk is repointing existing braid tests off config_root, pinned by an rg premise
---

# braid: read sources and policies from buvis-braid.yaml

Source: GitHub issue buvis/gems#272. Depends on PRD 00122 (machine-local layer in `~/.local/.config/buvis/`).

## Overview

### Problem Statement

braid reads its sources from `~/.config/braid/sources.d/` and a `.braidignore` from `~/.config/braid/` (`BraidSettings.config_root` in `src/tools/braid/settings.py`, `read_configured_sources` and `resolve_settings` in `src/tools/braid/domain/engine.py`). Every other gems tool keeps its config in `~/.config/buvis/buvis-<tool>.yaml` through `buvis.pybase.configuration`. A separate tool directory breaks that convention and the dotfiles layout: shared config is tracked under `~/.config/buvis/`, machine-local values live under `~/.local/.config/buvis/` (PRD 00122).

### Target Users

The owner, running braid on several machines. The downstream machine migration (agent-skills PRD 00159, dotfiles PRD 00183) waits on this release and gates on `braid --help` no longer listing `--config-root`.

### Success Metrics

- `uv run pytest tests/tools/braid -k "buvis_braid_yaml or config_root or machine_local or relative_configured"` passes.
- `braid --help` output has no `--config-root` (`test_cli_help_does_not_offer_config_root`).
- `rg -n "sources\.d|config_root|config-root|CONFIG_ROOT|config/braid" src/tools/braid docs/source README.md AGENTS.md` prints nothing.
- Full gate green at the end: `uv run pytest`, `uv run mypy src/lib/ src/tools/`, `uv run sphinx-build -b html docs/source docs/build/html`.

## Functional Decomposition

### Capability: Sources and policies from buvis config

#### Feature: `sources` and `policies` settings

- **Description**: `BraidSettings` gains `sources` and `policies` lists, read from `buvis-braid.yaml` like any other gems setting.
- **Inputs**: Merged YAML from the loader (`~/.config/buvis/buvis-braid.yaml`, `~/.local/.config/buvis/buvis-braid.yaml`, `$BUVIS_CONFIG_DIR/buvis-braid.yaml`).
- **Outputs**: `BraidSettings.sources: tuple[Path, ...] = ()`, `BraidSettings.policies: tuple[Path, ...] = ()`.
- **Behavior**: Example shared file:

  ```yaml
  sources:
    - ~/git/src/github.com/buvis/agent-skills
  ```

  A machine-only source goes in `~/.local/.config/buvis/buvis-braid.yaml` as `sources+: [~/work/skills]` and is appended by the loader's existing list directives (`_apply_list_directives` in `src/lib/buvis/pybase/configuration/loader.py`); no braid code handles merging.

#### Feature: Compose request takes configured lists

- **Description**: `ComposeRequest` carries the configured lists instead of `config_root`.
- **Inputs**: `BraidSettings.sources`, `BraidSettings.policies`, CLI `--source`, CLI `--policy`.
- **Outputs**: `ComposeRequest` drops `config_root` and gains `configured_sources: tuple[Path, ...] = ()` and `configured_policies: tuple[Path, ...] = ()`. `cli.py` passes `configured_sources=settings.sources`, `configured_policies=settings.policies`; `sources` and `policies` stay the CLI values.
- **Behavior**: `resolve_settings` expands `~` in each configured entry with `_expand_user`; an entry that is still relative raises `BraidError(f"sources entry must be absolute or start with ~: {entry}")` (or `policies entry ...`) (guess). Sources = `_deduplicate([*configured_sources, *request.sources])`. Policy candidates, in order: `agents_root / ".braidignore"`, each source's policy root `.braidignore` (unchanged), `*configured_policies`, `*request.policies`; only existing files load, as today. With no source: `BraidError("no skill sources configured; add a path to sources in ~/.config/buvis/buvis-braid.yaml or pass --source")`.

#### Feature: Remove the braid config directory

- **Description**: Drop every trace of `~/.config/braid`.
- **Inputs**: None.
- **Outputs**: No `config_root` setting, no `--config-root` option, no `BUVIS_BRAID_CONFIG_ROOT`, no `read_configured_sources`, no `<config_root>/.braidignore` candidate.
- **Behavior**: No fallback: `~/.config/braid` was never deployed on the main machine. A stale `config_root:` key in a YAML file is ignored by the resolver (it merges only keys that are settings fields).

#### Feature: Kiro enrollment location check

- **Description**: Confirm saved Kiro enrollment is machine state outside `~/.config`.
- **Inputs**: `src/tools/braid/domain/engine.py`.
- **Outputs**: No code change when the premise holds.
- **Behavior**: Premise: enrollment is saved in the `kiro` key of `<agents_root>/.braid-state.json` (`state_path = settings.agents_root / ".braid-state.json"`, engine.py line 524), which is the agents root the issue allows. The task re-checks with `rg -n "braid-state.json" src/tools/braid`; if enrollment is written anywhere under `~/.config`, stop, change nothing, and record it in the review notes.

### Capability: Docs and changelog

#### Feature: Docs

- **Description**: Describe the YAML config everywhere `sources.d` or `--config-root` appears.
- **Inputs**: `docs/source/tools/braid.rst`, `docs/source/tools.rst`, `README.md`, `AGENTS.md`, `src/tools/braid/manifest.toml`.
- **Outputs**: Updated text.
- **Behavior**: `docs/source/tools/braid.rst`: intro (lines 6-7) says braid reads the repos listed under `sources` in `~/.config/buvis/buvis-braid.yaml`; the usage line 25 drops `--config-root DIR`; "Sources" (lines 42-61) shows the YAML example above and the `sources+:` machine-local example in `~/.local/.config/buvis/buvis-braid.yaml`, says entries must be absolute or start with `~`, and that with no source braid names `sources` in `~/.config/buvis/buvis-braid.yaml`; the `.braidignore` list (lines 71-74) replaces `<config_root>/.braidignore` with "each path in `policies` in `buvis-braid.yaml`"; the roots table drops the `--config-root` row (line 205); "Moving from agent-skills" (lines 209-215) says to put the paths from `sources.d` under `sources` in `~/.config/buvis/buvis-braid.yaml`. `docs/source/tools.rst:37`, `README.md:96`, `README.md:201`, `AGENTS.md:43` and the `description` in `src/tools/braid/manifest.toml:5` say "sources in `buvis-braid.yaml`" instead of `sources.d`.

#### Feature: Changelog

- **Description**: Record the breaking change.
- **Inputs**: None.
- **Outputs**: Under `## [Unreleased]` `### Removed`: `- **braid**: `--config-root`, `BUVIS_BRAID_CONFIG_ROOT` and the `~/.config/braid` directory (`sources.d`, `.braidignore`); list sources under `sources` and extra policy files under `policies` in `~/.config/buvis/buvis-braid.yaml`, machine-only ones as `sources+:` in `~/.local/.config/buvis/buvis-braid.yaml``.
- **Behavior**: Same commit as the code.

## Structural Decomposition

### Repository Structure

```text
src/tools/braid/settings.py              # sources, policies fields; config_root removed
src/tools/braid/cli.py                   # --config-root removed; passes configured lists
src/tools/braid/domain/engine.py         # ComposeRequest, resolve_settings; sources.d reader removed
src/tools/braid/manifest.toml            # tool description
docs/source/tools/braid.rst              # sources, policies, roots table, migration
docs/source/tools.rst                    # tool table line
README.md                                # tool table and braid section
AGENTS.md                                # architecture tree comment
CHANGELOG.md                             # Removed entry
tests/tools/braid/test_cli.py            # CLI tests off --config-root, new YAML tests
tests/tools/braid/test_engine.py         # sources.d reader test removed, resolve tests
tests/tools/braid/test_rules.py          # ComposeRequest without config_root
tests/tools/braid/test_rules_cli.py      # CLI rules tests off --config-root
```

### Module: braid settings and CLI

- **Location**: `src/tools/braid/settings.py`, `src/tools/braid/cli.py`
- **Maps to capability**: Sources and policies from buvis config
- **Responsibility**: Read config and build the compose request.
- **Exports**:
  - `BraidSettings.sources`, `BraidSettings.policies` - configured lists

### Module: braid engine

- **Location**: `src/tools/braid/domain/engine.py`
- **Maps to capability**: Sources and policies from buvis config
- **Responsibility**: Turn the request into resolved `Settings`.
- **Exports**:
  - `configured_sources`, `configured_policies` - new fields on `ComposeRequest`
  - `resolve_settings()` - validates, merges and dedupes sources and policies
- New symbols: `configured_sources`, `configured_policies`, `test_configured_sources_expand_home_and_come_before_cli_sources`, `test_relative_configured_source_is_refused`, `test_configured_policy_keeps_the_skill_out_of_claude`, `test_cli_help_does_not_offer_config_root`, `test_cli_check_passes_with_only_buvis_braid_yaml`, `test_machine_local_sources_append_to_shared_buvis_braid_yaml`

### Module: braid docs and changelog

- **Location**: `docs/source/tools/braid.rst`, `docs/source/tools.rst`, `README.md`, `AGENTS.md`, `src/tools/braid/manifest.toml`, `CHANGELOG.md`
- **Maps to capability**: Docs and changelog
- **Responsibility**: Describe the config and the breaking change.
- **Exports**: none.

## Dependency Graph

### Foundation Layer (Phase 0)

No dependencies inside this PRD. External: PRD 00122 must be done first (the machine-local append test reads `~/.local/.config/buvis`).

- **braid engine**: request shape and resolution.

### Core Layer (Phase 1)

- **braid settings and CLI**: Depends on [braid engine].

### Integration Layer (Phase 2)

- **braid docs and changelog**: Depends on [braid settings and CLI, braid engine].

## Implementation Phases

### Phase 0: Foundation

**Goal**: The engine resolves sources and policies from configured lists.

**Tasks**:

- [ ] In `src/tools/braid/domain/engine.py`, replace `ComposeRequest.config_root` with `configured_sources: tuple[Path, ...] = ()` and `configured_policies: tuple[Path, ...] = ()`; delete `read_configured_sources` and its `__all__` entry; rewrite `resolve_settings` as in the "Compose request takes configured lists" feature. Premise: `rg -c "config_root|sources\.d|read_configured_sources|BUVIS_BRAID_CONFIG_ROOT|write_sources|--config-root" tests/tools/braid` prints 3 for test_rules, 12 for test_cli, 6 for test_rules_cli and 4 for test_engine before the edit; if not, re-read those tests before repointing them. Repoint `tests/tools/braid/test_rules.py` and `tests/tools/braid/test_engine.py` off `config_root`; replace `test_configured_sources_support_comments_home_and_relative_paths` with `test_configured_sources_expand_home_and_come_before_cli_sources` and add `test_relative_configured_source_is_refused` and `test_configured_policy_keeps_the_skill_out_of_claude` (no deps) - Acceptance: `uv run pytest tests/tools/braid/test_engine.py tests/tools/braid/test_rules.py` passes.
- [ ] Re-check the Kiro premise with `rg -n "braid-state.json" src/tools/braid` (no deps) - Acceptance: enrollment is written only under the agents root and the code is unchanged; otherwise stop, change nothing, record it in the review notes.

**Exit Criteria**: The engine has no `config_root`.

### Phase 1: Core

**Goal**: CLI and settings read the lists from `buvis-braid.yaml`.

**Tasks**:

- [ ] In `src/tools/braid/settings.py`, delete `config_root` and add `sources: tuple[Path, ...] = ()` and `policies: tuple[Path, ...] = ()`; in `src/tools/braid/cli.py`, delete the `--config-root` option and parameter and pass `configured_sources=settings.sources, configured_policies=settings.policies` (depends on: Phase 0). Repoint `tests/tools/braid/test_cli.py` and `tests/tools/braid/test_rules_cli.py`: `roots()` drops `--config-root`; `write_sources` writes `buvis-braid.yaml` with a `sources` list into the `BUVIS_CONFIG_DIR` the braid conftest sets; the env test drops `BUVIS_BRAID_CONFIG_ROOT`; `test_cli_without_sources_names_the_braid_config_directory` asserts the new message names `~/.config/buvis/buvis-braid.yaml`. Add `test_cli_help_does_not_offer_config_root`, `test_cli_check_passes_with_only_buvis_braid_yaml` (sync then `--check` with no `--source`, exit 0), and `test_machine_local_sources_append_to_shared_buvis_braid_yaml` (unset `BUVIS_CONFIG_DIR`; `HOME/.config/buvis/buvis-braid.yaml` lists one source, `HOME/.local/.config/buvis/buvis-braid.yaml` has `sources+:` with a second; both sources' skills are linked) - Acceptance: `uv run pytest tests/tools/braid` passes; `rg -n "config_root|sources\.d|CONFIG_ROOT|config-root" src/tools/braid tests/tools/braid` prints nothing.

**Exit Criteria**: `braid --help` has no `--config-root`; braid runs from `buvis-braid.yaml` alone.

### Phase 2: Integration

**Goal**: Docs and changelog match.

**Tasks**:

- [ ] Update `docs/source/tools/braid.rst`, `docs/source/tools.rst`, `README.md`, `AGENTS.md` and `src/tools/braid/manifest.toml` as in the Docs feature (depends on: Phase 1) - Acceptance: `rg -n "sources\.d|config/braid|config-root|CONFIG_ROOT" docs/source README.md AGENTS.md src/tools/braid` prints nothing; `rg -n "buvis-braid.yaml" docs/source/tools/braid.rst` hits.
- [ ] Add the `### Removed` entry under `## [Unreleased]` in `CHANGELOG.md`, text as in the Changelog feature (depends on: Phase 1) - Acceptance: `rg -n "BUVIS_BRAID_CONFIG_ROOT" CHANGELOG.md` prints the new entry.

**Exit Criteria**: `uv run pytest`, `uv run mypy src/lib/ src/tools/` and `uv run sphinx-build -b html docs/source docs/build/html` pass.

## Test Strategy

### Critical Scenarios

- **Happy path**: `~/.config/buvis/buvis-braid.yaml` lists one source → Expected: sync links its skills; `braid --check` exits 0.
- **Edge case**: `~/.local/.config/buvis/buvis-braid.yaml` has `sources+: [<second>]` → Expected: both sources compose.
- **Edge case**: a source is in YAML and passed as `--source` → Expected: deduplicated, YAML first.
- **Error case**: no source anywhere → Expected: error names `sources` in `~/.config/buvis/buvis-braid.yaml`, with the same exit code as today's missing-sources error.
- **Error case**: YAML `sources: [skills]` (relative) → Expected: error names the entry, nothing written.

## Risks

- **Stale `~/.config/braid` on a machine**: ignored silently. The issue states it was never deployed on the main machine; the changelog names the move.
- **List directive on an empty base**: `sources+:` in the machine file with no shared `sources` must still yield a list; `test_machine_local_sources_append_to_shared_buvis_braid_yaml` covers the shared-plus-local case, and the loader's directive tests own the empty-base case.
