---
eligibility: test -f src/tools/braid/domain/engine.py
default_model: opus
model_tier_rationale: invented contracts - state schema, generated-file format and host file preservation rule are new and PRD-defined; a later repo (agent-rules) consumes them
---

# braid: add rules as a second composed kind

Source: `~/.claude/docs/dev/project-management/discovery/00182-layer-agent-rules-across-hosts.md` (phase 2 of 3). Depends on PRD 00115 (braid in gems).

## Overview

### Problem Statement

Skills share one format and one discovery path; always-on rules do not. Claude
Code and Kiro read a directory of Markdown files; Codex, Copilot CLI, Pi and
Gemini CLI read one file each, and Codex, Copilot and Pi have no imports. Today
all four single-file hosts and Kiro link to one hand-kept `~/.claude/AGENTS.md`.
Discovery 00182 makes rules a second braid kind: every source in `sources.d`
may carry `rules/` and `hosts/<host>/rules/`, braid unions them with the same
duplicate and `.braidignore` rules as skills, links them into directory hosts,
and generates one file per single-file host.

### Target Users

The user (public, company and machine-local layers) and colleagues consuming a
company source.

### Success Metrics

- Every test in `tests/tools/braid/test_rules.py` and
  `tests/tools/braid/test_rules_cli.py` passes.
- The PRD 00115 suites (`tests/tools/braid/test_engine.py`,
  `tests/tools/braid/test_check.py`, `tests/tools/braid/test_cli.py`) still pass.
- A source with only `skills/` produces byte-identical state and output to
  PRD 00115 behavior (`test_skill_only_source_keeps_the_skills_state_shape`).

## Functional Decomposition

### Capability: Rule discovery

#### Feature: Source layout
- **Description**: A source is a directory holding any of `skills/`, `rules/`, `hosts/`. A source that is itself named `skills` stays accepted, as before.
- **Inputs**: Configured sources.
- **Outputs**: Skill inventory (unchanged), shared rule inventory `{name: rule_dir}`, host rule inventory `{host: {name: rule_dir}}`.
- **Behavior**: A source with none of the three → `BraidError("source has no skills, rules or hosts directory: {source}")`. A shared rule is `rules/<name>/RULE.md`; a host rule is `hosts/<host>/rules/<name>/RULE.md`. Rule name = directory name and must match `^[a-z0-9-]+$`, else `BraidError`. `RULE.md` needs no frontmatter and is never parsed. Symlinked rule directories, dot-directories and directories without `RULE.md` are skipped, as for skills. Known hosts: `claude`, `kiro`, `codex`, `copilot`, `pi`, `gemini`; any other directory under `hosts/` → `BraidError("unknown host directory: {path}")`.

#### Feature: Merge and duplicates
- **Description**: Union of all sources in `sources.d` order.
- **Inputs**: Per-source inventories.
- **Outputs**: Merged inventories.
- **Behavior**: A shared rule name in two sources → `BraidError("duplicate rule name ...")`. A host rule whose name equals a shared rule name, or the same host rule name in two sources → the same error. Nothing shadows anything. Names live in their own namespace: a rule and a skill may share a name.

#### Feature: Ignore policy
- **Description**: `.braidignore` entries drop rule names exactly as they drop skill names.
- **Inputs**: Loaded policy files.
- **Outputs**: Eligible rule sets per host.
- **Behavior**: Ignored rules stay in the `~/.agents` union views and are removed from every host projection and every generated file, for all hosts (unlike skills, where Kiro ignores the policy). An ignored name counts once in `Result.ignored` per host projection.

### Capability: Rule projection

#### Feature: Union views
- **Description**: Per-rule directory links `~/.agents/rules/<name>` (shared) and `~/.agents/hosts/<host>/rules/<name>` (host).
- **Inputs**: Merged inventories.
- **Outputs**: Directory links, reusing the skills link, backup, stale-removal and orphan logic.
- **Behavior**: Same report lines and drift accounting as the skills union. `RULE.md` reference pointers (`~/.agents/rules/<name>/references/x.md`, `~/.agents/hosts/<host>/rules/<name>/references/x.md`) resolve through these links.

#### Feature: Directory hosts
- **Description**: `~/.claude/rules/<name>.md` (shared + `claude` rules, when Claude projection is on) and `<kiro-root>/steering/<name>.md` (shared + `kiro` rules, when Kiro is enrolled) are file links to the union view's `RULE.md`.
- **Inputs**: Eligible rules, `--no-claude`, Kiro enrollment.
- **Outputs**: File symlinks; backups under `<claude-root>/rules-backup/<suffix>/` and `<kiro-root>/steering-backup/<suffix>/`.
- **Behavior**: A same-name existing path is backed up then linked, as for skills. Files braid does not record (other names) are never touched; `--check` reports a link into a braid union root that the manifest does not record as `MISMATCH ORPHAN`. On Windows a file symlink that fails with winerror 5 or 1314 falls back to a hard link (`os.link`); a hard link counts as current when `os.path.samefile` holds against the `RULE.md` target.

#### Feature: Generated single-file host instructions
- **Description**: braid writes `~/.agents/hosts/<host>/AGENTS.md` for each of `codex`, `copilot`, `pi`, `gemini` on every run.
- **Inputs**: Eligible shared rules, eligible host rules for that host.
- **Outputs**: One UTF-8 file per host.
- **Behavior**: Content = line `<!-- Generated by braid. Edit the rule sources, not this file. -->`, a blank line, then each eligible shared `RULE.md`, then each eligible host `RULE.md`; each group ordered by source position in `sources.d`, then by name; each body has trailing whitespace stripped and bodies are joined by one blank line; the file ends with exactly one newline. Written with `atomic_write_text`. A file whose bytes differ from the expected content is drift: `MISMATCH GENERATED {path}` under `--check`, `WOULD GENERATE {path}` under `--dry-run`, `GENERATE {path}` on sync. When the content exceeds 32768 bytes braid emits `WARNING {path} is {n} bytes; Codex reads 32768 by default` (not drift).

#### Feature: Host instruction links
- **Description**: The host's own instruction path links to its generated file: `~/.codex/AGENTS.md`, `~/.copilot/copilot-instructions.md`, `~/.pi/agent/AGENTS.md`, `~/.gemini/GEMINI.md`.
- **Inputs**: Generated files, existing host paths.
- **Outputs**: File symlinks recorded in state.
- **Behavior**: braid creates the link only when the path is absent or already a link braid recorded. An existing path braid does not own (today each of the first three is a hand-made link to `~/.claude/AGENTS.md`) is never replaced or backed up: braid emits `UNMANAGED {path}` and counts it in a new `Result.unmanaged` counter, not as drift. The user removes such a path once to hand it to braid. The parent directory is created only when the host's root (`~/.codex`, `~/.copilot`, `~/.pi`, `~/.gemini`) already exists; a missing host root skips that host link silently.

#### Feature: State and summary
- **Description**: The manifest records rule links and generated files beside skills.
- **Inputs**: Previous state.
- **Outputs**: `.braid-state.json`, still `version: 1`.
- **Behavior**: An optional top-level `rules` object, written only when any rule projection exists: `{"union": {name: target}, "hosts": {host: {name: target}}, "projected": {"claude"|"kiro": {name: target}}, "generated": {host: path}, "instructions": {host: path}}`. A state without `rules` loads as empty rules; a malformed `rules` object → `BraidError("invalid rules state in {path}")`. The summary line gains `{unmanaged} unmanaged` after `{configured} configured`, and `{generated} generated` after `{linked} linked`.

## Structural Decomposition

### Repository Structure

```text
src/tools/braid/
├── cli.py                      # summary line gains generated + unmanaged
├── commands/compose/compose.py # metadata gains unmanaged
└── domain/
    ├── engine.py               # source layout, Result/State fields, run() calls rules
    └── rules.py                # Maps to: Rule discovery, Rule projection
tests/tools/braid/
├── conftest.py                 # make_rule, make_host_rule helpers
├── test_rules.py               # engine-level rule tests
└── test_rules_cli.py           # CLI summary and exit codes with rules
docs/source/tools/braid.rst     # rules section
CHANGELOG.md                    # Added entry
```

### Module: rules
- **Maps to capability**: Rule discovery, Rule projection
- **Responsibility**: Discover, merge, project and generate rules; no Click, no console.
- **Location**: `src/tools/braid/domain/rules.py`
- **Exports**:
  - `discover_rules(sources)` - returns `RuleInventory(shared, hosts)`
  - `render_host_file(shared, host_rules)` - returns the generated text
  - `sync_rules(settings, inventory, ignored, previous, result, emit)` - returns the next `RuleState`
  - `RuleInventory`, `RuleState` - frozen dataclasses
  - `KNOWN_HOSTS`, `SINGLE_FILE_HOSTS`, `HOST_INSTRUCTION_PATHS` - constants
- New symbols: `rules.py`, `discover_rules`, `render_host_file`, `sync_rules`, `RuleInventory`, `RuleState`, `KNOWN_HOSTS`, `SINGLE_FILE_HOSTS`, `HOST_INSTRUCTION_PATHS`

### Module: engine
- **Maps to capability**: Source layout, State and summary
- **Responsibility**: Accept rule-only sources, extend `Result` and `State`, call `sync_rules` after the skill projections and before orphan reporting.
- **Location**: `src/tools/braid/domain/engine.py`, `src/tools/braid/commands/compose/compose.py`, `src/tools/braid/cli.py`
- **Exports**:
  - `Result.generated`, `Result.unmanaged` - new counters
  - `State.rules` - optional `RuleState`
- New symbols: `unmanaged`, `generated`, `Result.unmanaged`, `Result.generated`, `State.rules`, `UNMANAGED`, `test_skill_only_source_keeps_the_skills_state_shape`, `test_existing_host_instruction_link_is_reported_unmanaged_and_kept`, `test_ignored_rule_leaves_every_host`, `test_malformed_rules_state_is_refused`, `test_missing_host_root_skips_the_instruction_link`, `test_oversized_generated_file_warns_without_drift`, `test_rule_removed_from_source_unlinks_from_claude_and_kiro`, `test_stale_generated_file_is_check_drift`, `test_windows_file_link_falls_back_to_hard_link`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **rules (discovery and render)**: `discover_rules`, `render_host_file`.

### Core Layer (Phase 1)
- **rules (projection)**: Depends on [rules discovery, engine link helpers from PRD 00115]
- **engine**: Depends on [rules projection]

### Integration Layer (Phase 2)
- **cli, compose, docs**: Depends on [engine]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Rules are discovered and rendered.

**Tasks**:
- [ ] Add `discover_rules`, `render_host_file` and the constants to `src/tools/braid/domain/rules.py`; relax the skills-directory check in `src/tools/braid/domain/engine.py` so a source needs any of `skills/`, `rules/`, `hosts/` (no deps) - Acceptance: `uv run pytest tests/tools/braid/test_rules.py -k "discover or render or layout or duplicate or unknown_host"` passes, covering: rule-only source accepted, empty source refused with the new message, invalid name refused, unknown host refused, shared/shared and shared/host duplicates refused, symlinked rule dir skipped, render order and header exact.

**Exit Criteria**: Discovery and render tests green.

### Phase 1: Core
**Goal**: Rules reach every host.

**Tasks**:
- [ ] Add `sync_rules` (union views, directory hosts, generated files, host instruction links) and wire it into `run()` with the `Result` and `State` extensions (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/braid/test_rules.py` passes, including `test_ignored_rule_leaves_every_host`, `test_existing_host_instruction_link_is_reported_unmanaged_and_kept`, `test_missing_host_root_skips_the_instruction_link`, `test_stale_generated_file_is_check_drift`, `test_oversized_generated_file_warns_without_drift`, `test_windows_file_link_falls_back_to_hard_link`, `test_rule_removed_from_source_unlinks_from_claude_and_kiro`, `test_malformed_rules_state_is_refused`, `test_skill_only_source_keeps_the_skills_state_shape`; the PRD 00115 suites still pass: `uv run pytest tests/tools/braid/test_engine.py tests/tools/braid/test_check.py`.

**Exit Criteria**: A sync over a temp home with one shared, one claude and one codex rule produces every link and file listed in Rule projection, and an immediate `--check` reports 0 drift.

### Phase 2: Integration
**Goal**: CLI and docs expose rules.

**Tasks**:
- [ ] Extend the summary line in `src/tools/braid/cli.py` and `metadata` in `src/tools/braid/commands/compose/compose.py`; add `tests/tools/braid/test_rules_cli.py` (depends on: Phase 1) - Acceptance: `uv run pytest tests/tools/braid/test_rules_cli.py tests/tools/braid/test_cli.py` passes; an unmanaged host path leaves `--check` at exit 0.
- [ ] Document rules in `docs/source/tools/braid.rst` (layout, host table, generated file format, unmanaged rule, Windows hard-link fallback) and add `CHANGELOG.md` `[Unreleased]` Added entry `- **braid**: compose always-on rules from rules/ and hosts/<host>/rules/ into Claude Code, Kiro and generated Codex, Copilot, Pi and Gemini instruction files` (depends on: Phase 2 first task) - Acceptance: `rg -n "hosts/<host>/rules" docs/source/tools/braid.rst` hits; `uv run sphinx-build -W -b html docs/source docs/build/html` exits 0.

**Exit Criteria**: Full gate green: `uv run pytest`, `uv run mypy src/lib/ src/tools/`, `uv run ruff check`.

## Test Strategy

### Critical Scenarios
- **Happy path**: shared + host rules over two sources → links, generated files and state as specified; second `--check` is clean.
- **Edge case**: `~/.codex/AGENTS.md` is a hand-made link → `UNMANAGED`, untouched, exit 0 under `--check`.
- **Edge case**: rule ignored by `.braidignore` → still in `~/.agents/rules`, absent from Claude, Kiro and all generated files.
- **Error case**: same rule name in two sources → `BraidError`, exit 2, nothing written.
- **Error case**: `hosts/vscode/` → `BraidError` naming the path.

## Risks

- **Codex loses its instructions on first sync**: prevented by the unmanaged rule; braid never replaces a host path it did not create.
- **Hard links go stale on Windows after `git checkout` rewrites `RULE.md`**: `--check` reports the link as drift (`samefile` fails) and the next sync relinks it.
- **Large generated files truncate in Codex**: the 32 KiB warning names the file; keeping `RULE.md` slim is a content rule for the agent-rules repo.
