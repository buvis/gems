---
default_model: opus
model_tier_rationale: equivalence obligation - the port must behave like agent-skills braid d535891 on every ported test, and the CLI layer is re-shaped onto Click and console
---

# braid: port the skill composer into gems at parity

Source: `~/.claude/docs/dev/project-management/discovery/00182-layer-agent-rules-across-hosts.md` (phase 1 of 3).

## Overview

### Problem Statement

`braid` composes skills from every source in `sources.d` into `~/.agents/skills`
and links them into `~/.claude/skills` and `~/.kiro/skills`. It lives in
`buvis/agent-skills` as the `agent-skills-braid` package, so a content repo
carries machine tooling, braid is not on PATH (it runs through the
`~/.agents/bin/braid` link), and a colleague who wants only a company source
must clone the personal skills repo. Discovery 00182 moves braid into gems as
`src/tools/braid/`, per the gems tool standard, before the rules kind (PRD 00116)
lands on top of it.

Reference implementation: `buvis/agent-skills` at commit d535891, files
`src/agent_skills_braid/cli.py` (799 lines), `tests/test_braid.py` and
`tests/test_braid_check.py`. Read them from that checkout
(`~/git/src/github.com/buvis/agent-skills`); do not copy them by hand-retyping.

### Target Users

The user on every machine (macOS and Windows), and colleagues who install
`buvis-gems` to consume a company source.

### Success Metrics

- Every test ported from the two reference suites passes under
  `uv run pytest tests/tools/braid`, with the exceptions listed in Phase 2.
- `uv run python tools/lib/check_tool_wiring.py` exits 0 with braid wired.
- `uv run braid --help` lists every option the reference CLI has, minus `--version`
  (now supplied by `buvis_options`).

## Functional Decomposition

### Capability: Skill composition (ported unchanged)

#### Feature: Inventory, union and host projection
- **Description**: Same behavior as the reference `run()`: discover skills, reject duplicates, link the union, project to Claude and Kiro, back up collisions, remove stale manifest-owned links, report orphans in read-only modes, persist the manifest.
- **Inputs**: `Settings` (sources, roots, mode, policy files, Kiro flags).
- **Outputs**: `Result` counters plus emitted report lines (`LINK[...]`, `BACKUP`, `REMOVE`, `MISMATCH ...`, `WOULD ...`, `CONFIGURE`).
- **Behavior**: Byte-for-byte the reference line formats. Windows junction fallback kept. Only two deliberate changes: the state file is written with `buvis.pybase.filesystem.atomic_write_text` (gems atomic-persistence invariant), and any `OSError` from it is still raised as `BraidError("cannot write Braid state {path}: {error}")`.

#### Feature: Kiro enrollment and agent resources
- **Description**: Same behavior as the reference `select_kiro`, `prepare_kiro_agents`, `sync_kiro_agent`.
- **Inputs**: Kiro flags and the saved registration.
- **Outputs**: Edited agent JSON files with backups.
- **Behavior**: Unchanged, including the compare-before-replace race check. The agent rewrite keeps its own tempfile plus `os.replace`, because `atomic_write_bytes` has no compare step; this is not a bare write, so the invariant holds.

### Capability: Gems CLI surface

#### Feature: Click command
- **Description**: `braid` is a single Click command (not a group) decorated with `buvis_options(settings_class=BraidSettings)`.
- **Inputs**: `--dry-run`, `--check`, `--source PATH` (multiple), `--policy PATH` (multiple), `--agents-root`, `--claude-root`, `--config-root`, `--no-claude`, `--kiro`, `--kiro-root`, `--kiro-agent NAME` (multiple), `--forget-kiro-agent NAME` (multiple), `--no-kiro`. Help texts copied from the reference `_parser()`.
- **Outputs**: Report lines and the summary line `braid: {linked} linked, {current} current, {ignored} ignored, {removed} removed, {backed_up} backed up, {configured} configured, {drift} {drift|change(s)}`, all through `console`.
- **Behavior**: `--dry-run` with `--check` is rejected inside the callback. `--no-kiro` with any Kiro enrollment option is rejected with the reference message `--no-kiro cannot be combined with Kiro enrollment options`. Both rejections exit 2. Exit codes keep the reference contract: 0 success, 1 when `--check` finds drift, 2 on `BraidError` (the message is printed once through `console.failure`, then `ctx.exit(2)`; `console.panic` is not used because it exits 1).

#### Feature: Settings and configuration root
- **Description**: `BraidSettings(GlobalSettings)` with `env_prefix="BUVIS_BRAID_"` and fields `agents_root` (default `~/.agents`), `claude_root` (default `~/.claude`), `config_root` (default `~/.config/braid`), `kiro_root` (default `None`).
- **Inputs**: Environment `BUVIS_BRAID_AGENTS_ROOT`, `BUVIS_BRAID_CLAUDE_ROOT`, `BUVIS_BRAID_CONFIG_ROOT`, `BUVIS_BRAID_KIRO_ROOT`; CLI flags win over settings.
- **Outputs**: Resolved roots.
- **Behavior**: The reference env names `AGENTS_ROOT`, `CLAUDE_ROOT`, `KIRO_ROOT` and `AGENT_SKILLS_CONFIG` are dropped. `~/.config/agent-skills` is never read: no fallback (discovery 00182 decision). A non-empty `BUVIS_BRAID_KIRO_ROOT` enrolls Kiro exactly as `KIRO_ROOT` did.

#### Feature: Source and policy discovery without a home repository
- **Description**: The reference adds its own repository as an implicit source (`_repository_root()`). gems is not a skill repository, so that source and the `repository_root / ".braidignore"` policy candidate are removed.
- **Inputs**: `sources.d` files under the config root, `--source` flags.
- **Outputs**: Ordered, de-duplicated sources; policy files from `agents_root/.braidignore`, `config_root/.braidignore`, each source's `.braidignore`, and `--policy`.
- **Behavior**: No sources → `BraidError("no skill sources configured; add a path under {config_root}/sources.d or pass --source")`, exit 2.

## Structural Decomposition

### Repository Structure

```text
src/tools/braid/
├── __init__.py                 # __version__, __all__
├── __main__.py                 # from braid.cli import cli; cli()
├── cli.py                      # Maps to: Click command
├── settings.py                 # Maps to: Settings and configuration root
├── manifest.toml               # tool manifest (cli = true only)
├── commands/
│   ├── __init__.py
│   └── compose/
│       ├── __init__.py
│       └── compose.py          # Maps to: Click command (CommandCompose -> CommandResult)
└── domain/
    ├── __init__.py
    ├── engine.py               # Maps to: Inventory, union and host projection
    └── kiro.py                 # Maps to: Kiro enrollment and agent resources
tests/tools/braid/
├── __init__.py
├── conftest.py                 # make_skill, settings helpers; clears BUVIS_BRAID_* env
├── test_engine.py              # ported tests/test_braid.py (engine cases)
├── test_check.py               # ported tests/test_braid_check.py
└── test_cli.py                 # CLI cases via click.testing.CliRunner
pyproject.toml                  # [project.scripts], wheel packages, markers
README.md                       # tool count and table
AGENTS.md                       # Architecture tree lists braid
docs/source/tools.rst           # table row + toctree entry
docs/source/tools/braid.rst     # tool page
CHANGELOG.md                    # Added entry
```

### Module: domain
- **Maps to capability**: Skill composition
- **Responsibility**: Pure composition logic, no Click, no console. Emits report lines through an `emit` callable.
- **Location**: `src/tools/braid/domain/engine.py`, `src/tools/braid/domain/kiro.py`
- **Exports**:
  - `run(settings, emit)` - the reference `run()`
  - `Settings`, `Mode`, `Result`, `State`, `BraidError` - reference types (`Settings` here is the engine dataclass, not the pydantic class)
  - `discover_inventory`, `read_configured_sources`, `read_ignored`, `create_directory_link` - reference helpers
  - `KiroRegistration`, `KiroAgentEdit`, `select_kiro`, `prepare_kiro_agents`, `sync_kiro_agent` - from `kiro.py`
- New symbols: `engine.py`, `kiro.py`

### Module: commands
- **Maps to capability**: Gems CLI surface
- **Responsibility**: Wrap `run()`; catch `BraidError`; return `CommandResult`.
- **Location**: `src/tools/braid/commands/compose/compose.py`
- **Exports**:
  - `CommandCompose(settings).execute()` - returns `CommandResult(success, output, error, metadata={"drift": int, "exit_code": 0|1|2})`, with report lines joined into `output`
- New symbols: `CommandCompose`

### Module: cli
- **Maps to capability**: Gems CLI surface
- **Responsibility**: Parse options, resolve sources and policies, build the engine `Settings`, render the `CommandResult`, map the exit code.
- **Location**: `src/tools/braid/cli.py`, `src/tools/braid/settings.py`
- **Exports**:
  - `cli` - the Click command
  - `BraidSettings` - pydantic settings
- New symbols: `BraidSettings`, `BUVIS_BRAID_AGENTS_ROOT`, `BUVIS_BRAID_CLAUDE_ROOT`, `BUVIS_BRAID_CONFIG_ROOT`, `BUVIS_BRAID_KIRO_ROOT`, `test_cli_check_exits_1_on_drift`, `test_cli_never_reads_the_old_agent_skills_config`, `test_cli_rejects_dry_run_with_check`, `test_cli_without_sources_names_the_braid_config_directory`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **domain**: ported engine and Kiro logic.

### Core Layer (Phase 1)
- **commands**: Depends on [domain]
- **cli**: Depends on [commands, domain]

### Integration Layer (Phase 2)
- **wiring and docs** (`pyproject.toml`, `README.md`, `AGENTS.md`, `docs/source/tools.rst`, `docs/source/tools/braid.rst`, `CHANGELOG.md`): Depends on [cli]

## Implementation Phases

### Phase 0: Foundation
**Goal**: The engine runs inside gems.

**Tasks**:
- [ ] Port reference `cli.py` lines 1-629 into `src/tools/braid/domain/engine.py` and `src/tools/braid/domain/kiro.py` (Kiro dataclasses and the three Kiro functions in `kiro.py`), changing only imports and `_write_state` (now `atomic_write_text`, `OSError` re-raised as the same `BraidError` text) (no deps) - Acceptance: `uv run python -c "from braid.domain.engine import run, BraidError, Mode"` exits 0, and `rg -n "print\(" src/tools/braid/domain` finds nothing.
- [ ] Port `tests/test_braid.py` engine cases (every case not driving `main`/`entrypoint`/`_parser`) to `tests/tools/braid/test_engine.py` and `tests/test_braid_check.py` to `tests/tools/braid/test_check.py`, rewriting only imports and helpers; drop `test_a_failed_temp_cleanup_does_not_hide_the_state_write_error` (it tests the replaced temp-file code) and rewrite `test_a_failed_state_write_reports_a_braid_error_and_leaves_no_temp_file` to assert the state directory holds no entry besides the blocking directory (depends on: engine port) - Acceptance: `uv run pytest tests/tools/braid/test_engine.py tests/tools/braid/test_check.py` passes; premise check before the port: `rg -c "^def test_" tests/test_braid.py tests/test_braid_check.py` in the reference checkout reports 31 and 13; if it does not, port what is there and report the new counts.

**Exit Criteria**: Engine suites green inside gems.

### Phase 1: Core
**Goal**: `braid` works as a gems CLI.

**Tasks**:
- [ ] Add `src/tools/braid/settings.py` (`BraidSettings`, fields and env prefix as specified), `src/tools/braid/commands/compose/compose.py` (`CommandCompose`), `src/tools/braid/cli.py`, `src/tools/braid/__init__.py`, `src/tools/braid/__main__.py`, `src/tools/braid/manifest.toml`, `src/tools/braid/commands/__init__.py`, `src/tools/braid/commands/compose/__init__.py`, `src/tools/braid/domain/__init__.py` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/braid/test_cli.py` passes.
- [ ] Write `tests/tools/braid/test_cli.py` porting the reference CLI cases to `CliRunner`: `test_cli_loads_machine_policy_from_agents_root`, `test_cli_enrolls_kiro_and_reports_the_configured_agent`, `test_cli_enrolls_kiro_from_the_environment` (now `BUVIS_BRAID_KIRO_ROOT`), `test_cli_rejects_no_kiro_combined_with_enrollment` (exit 2), `test_cli_reports_a_failed_state_write_on_one_line_and_exits_2`, `test_cli_reports_an_unreadable_state_file_on_one_line_and_exits_2`, `test_parser_documents_previously_bare_options_with_help_text` (asserts each option's help text appears in `--help`); add `test_cli_check_exits_1_on_drift`, `test_cli_rejects_dry_run_with_check`, `test_cli_never_reads_the_old_agent_skills_config` (a `sources.d/personal` under a fake `~/.config/agent-skills` is ignored and the run exits 2 with the no-sources message), `test_cli_without_sources_names_the_braid_config_directory` (depends on: Phase 1 first task) - Acceptance: `uv run pytest tests/tools/braid/test_cli.py` passes; `tests/tools/braid/conftest.py` autouse fixture deletes every `BUVIS_BRAID_*` variable.

**Exit Criteria**: `uv run braid --help` exits 0 and `uv run braid --check --source <tmp source> --agents-root <tmp> --claude-root <tmp> --config-root <tmp> --no-kiro` behaves as the reference.

### Phase 2: Integration
**Goal**: braid ships in the wheel and is documented.

**Tasks**:
- [ ] Wire `pyproject.toml`: `braid = "braid.cli:cli"` in `[project.scripts]`, `"src/tools/braid",` in wheel packages, `"braid: braid tests",` in markers, all in alphabetical position (depends on: Phase 1) - Acceptance: `uv run python tools/lib/check_tool_wiring.py` exits 0; `uv run pytest -m braid` collects only `tests/tools/braid`.
- [ ] Document: add braid to the `README.md` CLI list (count 15 -> 16) and table, the `AGENTS.md` Architecture tree, a row and toctree entry in `docs/source/tools.rst`, and `docs/source/tools/braid.rst` (usage, sources.d under `~/.config/braid`, `.braidignore`, Kiro enrollment, exit codes, env names); add `CHANGELOG.md` `[Unreleased]` Added entry `- **braid**: compose agent skills from sources.d into ~/.agents and project them to Claude Code and Kiro (ported from agent-skills)` (depends on: Phase 2 first task) - Acceptance: `rg -n "braid" README.md AGENTS.md docs/source/tools.rst CHANGELOG.md` hits each file; `uv run sphinx-build -W -b html docs/source docs/build/html` exits 0.

**Exit Criteria**: Full gate green: `uv run pytest`, `uv run mypy src/lib/ src/tools/`, `uv run ruff check`.

## Test Strategy

### Critical Scenarios
- **Happy path**: two sources, one ignored skill → union holds both, Claude only the eligible one, state written (ported `test_sync_composes_union_and_projects_only_eligible_skills`).
- **Edge case**: lost state file under `--check` → reports state drift, not wanted links (ported).
- **Edge case**: Windows privilege failure → junction fallback (ported).
- **Error case**: unreadable state → one `console.failure` line, exit 2.
- **Error case**: config only under the old `~/.config/agent-skills` → ignored, exit 2 naming `~/.config/braid/sources.d`.

## Risks

- **Machines lose braid's sources on upgrade**: no fallback by design. PRD 00183 (buvis home) moves this machine's `sources.d` to `~/.config/braid` once this release is installed; the CHANGELOG entry names the move.
- **`braid` top-level module name clash**: the wheel installs into an isolated tool venv (`uv tool` / mise pipx), so a PyPI package named `braid` cannot share the environment.
- **Console markers change the line format**: tests assert message substrings and exit codes, not raw stderr bytes; no known script parses braid output.
