---
design: run
default_model: opus
model_tier_rationale: equivalence obligation - preserve source validation and bim format round trips
---

# bim tiromex: format and foundation commands

Source: [Discovery 00149](docs/dev/project-management/intake/processed/00149-merge-klyreon-into-bim/discovery.md); its adjacent port-plan.md supplies the approved inventory. Discovery takes precedence over older idea/Q&A/port examples. Part 1 of 6; the discovery explicitly reserves 00150–00155 instead of reusing 00149.

Grounding: `BimSettings` is defined at `src/tools/bim/settings.py:9-23`; `CommandExportClaims` at `src/tools/klyreon/commands/export_claims.py:19-27` supplies the preserved export contract.

## Overview

### Problem Statement
Fold the approved claim model into ordinary bim notes without giving tx access to the owner's private notes. Covers M1–M8, M11–M12, foundation M22/M28/M29; journal writing belongs to 00153.

### Target Users
The vault owner and unattended agents using bim; tests use scratch vaults, isolated HOME and XDG_STATE_HOME, never the private vault.

### Success Metrics
`uv run pytest tests/tools/bim/tx/test_format.py tests/tools/bim/tx/test_scope.py tests/tools/bim/tx/test_commands.py tests/tools/bim/tx/test_settings.py tests/tools/bim/test_format_note.py` passes, including a full format round trip and unchanged outside-vault sentinels.

## Functional Decomposition

### Capability: Tiromex note contract
#### Feature: Scoped note kinds
- **Description**: Recognize the configurable tiromex folder beneath path_zettelkasten.
- **Inputs**: BimSettings; scratch vault notes.
- **Outputs**: Confined paths and note-kind classification.
- **Behavior**: Default folder is tiromex; reject traversal, absolute and symlink escapes. All tiromex notes need id/title/date/type only. Apply tx-specific rules only to concept-type notes, index notes and tx-run notes; plain agent notes remain untouched. Non-tiromex notes never enter claims or backend context. The vault root is the parent of path_zettelkasten, matching CommandCreateNote.
#### Feature: Bim format and validation
- **Description**: Keep one bim representation with claim metadata and backmatter relations.
- **Inputs**: Existing bim parser/formatter; klyreon spec fixtures and enums.
- **Outputs**: Bim notes, index notes, tx-run type and mechanical diagnostics.
- **Behavior**: Use id/title/date/tags/type/publish/processed in bim order, H1 title and final backmatter separator. Preserve unknown keys and nested concept-type/assent/lifecycle/claims/doubts/updated/reviewed/delivered-as fields. Retain source claim/doubt enums, 1–3 claims when present, required claims for thesis/argument/observation and none for aporia; ten relations and transitive-cycle checks. Relations and parent are vault-relative titled wikilinks confined to tiromex; doubt targets use vault-relative tiromex paths. Index notes have § titles and tx:members blocks. Source values use mirror:<root>/<path>; resolution lands in 00152. Never emit person/book/colon tags or publish true. No oversized-body rule for run notes. Reuse dynamic ZettelData; do not add a second persisted model.
### Capability: Foundation commands
#### Feature: Create, validate, export and status
- **Description**: Expose bim tx new/validate/export-claims/status as CommandResult commands.
- **Inputs**: Existing --title/--type/--concept-type, validate --json, export --out flags.
- **Outputs**: Created note; validation JSON; claim JSON; status dashboard.
- **Behavior**: Port command behavior and output keys from source command modules. New uses bim creation and id/date collision bump with tentative/fleeting defaults and starter claim. Validation exits 1 on errors. Export retains schema_version/generated/claims and rejected claims; --out refuses the entire vault, including symlink aliases. Status reports lifecycle, assent, links, aporias and prune candidates; mirror pending counts finish in 00153. Staleness warns once on tx only. JSON renders through the console adapter without marker, wrapping or markup corruption; json.loads(stdout) must succeed.
#### Feature: Settings and operator guidance
- **Description**: Ship the tiromex exception without weakening the remaining vault approval rule.
- **Inputs**: Source KlyreonSettings and bim SKILL.
- **Outputs**: tx settings, CLI wiring, revised tiromex format specification.
- **Behavior**: Port max_sources_per_run=5, source_timeout_seconds=900, max_zettel_body_lines=60, maintenance_window_days=7, pruning_enabled=false, prune_window_days=365; named backend defaults claude; git identity defaults bim-tx/bim-tx@localhost. Honor BUVIS_BIM_TX__ overrides and reject unknown settings. Add the skill's tiromex concept/vocabulary/claim/doubt/conflict/command section. Do not port init, root config, assets or installed skill lookup.

## Structural Decomposition

### Repository Structure
```text
src/tools/bim/commands/tx/  # note contract and foundation commands
src/tools/bim/             # integration files enumerated below
tests/tools/bim/tx/        # focused tests enumerated below
docs/reference/bim/tiromex/zettel-format-specification.md
```

### Module: Note contract
- **Maps to capability**: Tiromex note contract
- **Location**: `src/tools/bim/commands/tx/__init__.py`, `src/tools/bim/commands/tx/cli.py`, `src/tools/bim/commands/tx/new.py`, `src/tools/bim/commands/tx/validate.py`, `src/tools/bim/commands/tx/export_claims.py`, `src/tools/bim/commands/tx/status.py`, `src/tools/bim/commands/tx/shared/__init__.py`, `src/tools/bim/commands/tx/shared/settings.py`, `src/tools/bim/commands/tx/shared/paths.py`, `src/tools/bim/commands/tx/shared/format.py`, `src/tools/bim/commands/tx/shared/validator.py`, `src/tools/bim/commands/tx/shared/claims.py`
- **Responsibility**: Confined bim note parsing, validation, claim export and CommandResult command classes.
- **Exports**: Confined bim note parsing, validation, claim export and CommandResult command classes.
New symbols: `src/tools/bim/commands/tx/__init__.py`, `src/tools/bim/commands/tx/cli.py`, `src/tools/bim/commands/tx/new.py`, `src/tools/bim/commands/tx/validate.py`, `src/tools/bim/commands/tx/export_claims.py`, `src/tools/bim/commands/tx/status.py`, `src/tools/bim/commands/tx/shared/__init__.py`, `src/tools/bim/commands/tx/shared/settings.py`, `src/tools/bim/commands/tx/shared/paths.py`, `src/tools/bim/commands/tx/shared/format.py`, `src/tools/bim/commands/tx/shared/validator.py`, `src/tools/bim/commands/tx/shared/claims.py`
### Module: Integration
- **Maps to capability**: Foundation commands
- **Location**: `src/tools/bim/cli.py`, `src/tools/bim/settings.py`, `src/tools/bim/dependencies.py`, `src/tools/bim/manifest.toml`, `src/tools/bim/SKILL.md`, `docs/source/tools/bim.rst`, `CHANGELOG.md`, `tests/tools/bim/tx/conftest.py`, `tests/tools/bim/tx/test_format.py`, `tests/tools/bim/tx/test_scope.py`, `tests/tools/bim/tx/test_commands.py`, `tests/tools/bim/tx/test_settings.py`, `tests/tools/bim/test_format_note.py`, `docs/reference/bim/tiromex/zettel-format-specification.md`
- **Responsibility**: BimSettings, lazy tx CLI registration, docs and regression fixtures.
- **Exports**: BimSettings, lazy tx CLI registration, docs and regression fixtures.
New symbols: `tests/tools/bim/tx/conftest.py`, `tests/tools/bim/tx/test_format.py`, `tests/tools/bim/tx/test_scope.py`, `tests/tools/bim/tx/test_commands.py`, `tests/tools/bim/tx/test_settings.py`, `docs/reference/bim/tiromex/zettel-format-specification.md`

## Dependency Graph

### Foundation Layer (Phase 0)
- **Note contract**: No new dependency; uses existing bim zettel APIs and source enums/validator as read-only port input.

### Core Layer (Phase 1)
- **Foundation commands** (within Note contract): Depends on [Note contract].

### Integration Layer (Phase 2)
- **Integration**: Depends on [Note contract, Foundation commands]. Serve/TUI dispatch is completed in 00154, before retirement.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Establish the isolated format.

**Tasks**:
- [ ] Add settings, confined path resolution and note-kind dispatch (no deps). Acceptance: `uv run pytest tests/tools/bim/tx/test_settings.py tests/tools/bim/tx/test_scope.py` rejects escapes and proves plain/outside notes excluded.
- [ ] Port folded format and mechanical validator using bim APIs (depends on: settings and paths). Acceptance: `uv run pytest tests/tools/bim/tx/test_format.py tests/tools/bim/test_format_note.py` covers converted valid/invalid rule fixtures, unknown keys, relations and tx-run round trip.

**Exit Criteria**: Format/scope tests pass; no source package imports in the new implementation.

### Phase 1: Core
**Goal**: Deliver usable commands.

**Tasks**:
- [ ] Add new, validate, export-claims and status command classes (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/tx/test_commands.py` checks creation, collisions, JSON decoding, exact export keys, rejected claims, outside-root --out refusal and one staleness line.

**Exit Criteria**: All four commands return CommandResult and confine their note reads/writes.

### Phase 2: Integration
**Goal**: Integrate and document the contract.

**Tasks**:
- [ ] Wire lazy CLI and composition, update manifest, skill, format spec, bim docs and changelog (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/bim/tx/test_commands.py -k integration` asserts CLI help, fixture query/show visibility, shipped skill exception and unchanged approval rule outside tiromex.

**Exit Criteria**: `uv run pytest` and `uv run mypy src/lib/ src/tools/` pass once at closeout.

## Test Strategy

### Critical Scenarios
- **Happy path**: concept note → format → parse preserves nested metadata and relations.
- **Edge case**: plain tiromex note has only base fields and validates; outside note with claims is never exported.
- **Error case**: malformed claim/doubt/relation, escape and cyclic transitive relation retain source rule diagnostics.
- **Integration**: source fixtures are converted in test builders; no dependency on the retiring package remains.

## Risks

- **Format drift**: source enums and validator fixtures are the parity oracle; do not silently replace their rules.
- **Premise**: bim already preserves arbitrary metadata; confirm with the round-trip tests before changing shared library code. If false, skip that unsupported change and report the evidence rather than widen this PRD.
- **Interface timing**: foundation classes land here; 00154 completes adapters before any old tool is removed.
