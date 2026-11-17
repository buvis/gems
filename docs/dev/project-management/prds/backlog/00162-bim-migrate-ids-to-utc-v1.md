---
default_model: opus
model_tier_rationale: destructive blast radius (renames notes and rewrites links across a vault) and an invented rewrite algorithm
---

# bim: migrate existing note ids to UTC

## Overview

### Problem Statement
Existing notes carry local-time ids (PRD 00161 switches new ids to UTC). The vault must move to one standard. Each note needs a new id, a new file name, and every reference to the old id updated. Some `date` fields have no time zone.

### Target Users
The vault owner, running the migration once per vault.

### Success Metrics
- After `bim migrate-ids --apply`, every note id equals the UTC digits of its `date`, or the note is listed as skipped with a reason.
- No wikilink, embed, or backmatter reference to an old id remains.
- `bim migrate-ids --undo MAPFILE` restores every file name, `id`, and `date` it changed.
- A dry run changes no file.

## Functional Decomposition

### Capability: Plan

#### Feature: Resolve the time zone
- **Description**: Decide the UTC instant of each note.
- **Inputs**: The `date` frontmatter value and the old id.
- **Outputs**: A timezone-aware date, and a flag `date_changed`.
- **Behavior**: A `date` with an offset keeps it. A `date` without an offset is read as `Europe/Prague` local time with DST (CET or CEST) through `zoneinfo`, and the offset is written into `date`. A local time that does not exist or repeats (DST change) is skipped and reported. A note without `date` takes the digits of its old id as `Europe/Prague` local time.

#### Feature: Build the mapping
- **Description**: Map each old id to a new id.
- **Inputs**: The resolved dates and all notes in `path_zettelkasten`.
- **Outputs**: A mapping `old id -> new id`, plus skipped notes with reasons.
- **Behavior**: New id = UTC digits (`%Y%m%d%H%M%S`). When two notes share a new id, or a new id is held by a note that is not itself being renamed, the later note (by old id) takes seconds `60`, `61`, up to `99`; after `99` the note is skipped and reported. A note whose new id equals its old id is left alone.

### Capability: Apply and undo

#### Feature: Apply
- **Description**: Rewrite the vault from the mapping.
- **Inputs**: The mapping and `--apply`.
- **Outputs**: Renamed files, updated frontmatter, updated references, and a map file.
- **Behavior**: First write the map file (JSON, old and new id, old and new `date`) outside the notes tree. Then rename each file with an atomic move, update `id` and `date`, and rewrite references in every `.md` file of the vault: `[[notes/<old>|...]]`, `[[notes/<old>]]`, `![[notes/<old>#...]]`, `[[<old>...]]` and Dataview `key:: [[...]]` values. Do not touch code fences or inline code. Stop at the first error and leave the map file in place.

#### Feature: Dry run and undo
- **Description**: Show the plan without writing; reverse an applied run.
- **Inputs**: No flag (dry run), or `--undo MAPFILE`.
- **Outputs**: A table of planned changes; or restored files.
- **Behavior**: The default is a dry run that prints the plan and the count of references to rewrite. `--undo` applies the reverse mapping the same way. Files that changed since the apply are skipped and reported.

## Structural Decomposition

### Repository Structure

```
src/tools/bim/
├── commands/migrate_ids/migrate_ids.py   # Maps to: Plan, Apply, Dry run and undo
├── params/migrate_ids.py                 # Maps to: Dry run and undo
├── note_write_cli.py                     # Maps to: wiring of the command (guess)
└── SKILL.md                              # Maps to: documents the command
tests/tools/bim/commands/test_migrate_ids.py
```

### Module: migrate_ids
- **Maps to capability**: Plan; Apply and undo
- **Responsibility**: Compute the mapping, apply it, and undo it.
- **Exports**:
  - `plan_migration()` - build the mapping and the skip list.
  - `apply_migration()` - write the map file, rename, rewrite.
  - `undo_migration()` - reverse a map file.
- New symbols: `plan_migration`, `apply_migration`, `undo_migration`, `CommandMigrateIds`, `date_changed`, `zoneinfo`

### Module: tests
- **Maps to capability**: all
- **Responsibility**: One test per rule, in `tests/tools/bim/commands/test_migrate_ids.py`.
- New symbols: `prague_dst_summer_offset`, `prague_dst_winter_offset`, `aware_date_keeps_offset`, `ambiguous_dst_time_is_skipped`, `same_new_id_gets_suffix_60`, `apply_rewrites_all_reference_forms`, `code_fences_untouched`, `undo_restores_bytes`, `dry_run_writes_nothing`, `migrate_ids_help_lists_apply_and_undo`

## Dependency Graph

### Foundation Layer (Phase 0)
- **migrate_ids (plan)**: depends on the UTC id rule from PRD 00161; no dependency inside this PRD.

### Core Layer (Phase 1)
- **migrate_ids (apply, undo)**: Depends on [migrate_ids (plan)]

### Integration Layer (Phase 2)
- **params and CLI wiring, SKILL.md**: Depends on [migrate_ids (apply, undo)]

## Implementation Phases

### Phase 0: Plan
**Goal**: A dry-run plan is correct on a fixture vault.

**Tasks**:
- [ ] Write `plan_migration` (depends on: PRD 00161 done) - Acceptance: tests `prague_dst_summer_offset`, `prague_dst_winter_offset`, `aware_date_keeps_offset`, `ambiguous_dst_time_is_skipped`, `same_new_id_gets_suffix_60` in `tests/tools/bim/commands/test_migrate_ids.py` pass.

**Exit Criteria**: Plan tests pass.

### Phase 1: Apply and undo
**Goal**: Apply and undo are lossless on a fixture vault.

**Tasks**:
- [ ] Write `apply_migration` and `undo_migration`. Premise: the vault is the scratch fixture in tests; at execution re-check that the target path is the configured `path_zettelkasten` and that the map file path is outside it; a failed premise means abort, never force (depends on: Phase 0) - Acceptance: tests `apply_rewrites_all_reference_forms`, `code_fences_untouched`, `undo_restores_bytes` (compare a hash of every file before and after apply plus undo), `dry_run_writes_nothing` pass.

**Exit Criteria**: Apply and undo tests pass.

### Phase 2: Integration
**Goal**: The command is reachable and documented.

**Tasks**:
- [ ] Add `params/migrate_ids.py`, wire `bim migrate-ids` in `note_write_cli.py`, add a short SKILL.md section (depends on: Phase 1) - Acceptance: test `migrate_ids_help_lists_apply_and_undo` runs `bim migrate-ids --help` and passes.
- [ ] Add a `CHANGELOG.md` entry under Added for bim (depends on: Phase 1) - Acceptance: `rg -c "migrate-ids" CHANGELOG.md` prints `1` or more.

**Exit Criteria**: The project test gate passes (`uv run pytest tests/tools/bim`).

## Test Strategy

### Critical Scenarios
- **Happy path**: a vault with 3 notes, one with `+02:00`, one with `+01:00`, one naive; all get UTC ids and all links update.
- **Edge case**: two notes map to the same UTC second; the later one gets seconds `60`.
- **Error case**: a naive date inside the autumn DST overlap is skipped and listed; the apply stops on a write error and `undo` restores the already changed files.

## Risks

- **The vault is large and links come in many forms**: an unlisted form leaves a dead link. Mitigation: the apply ends with a scan for every old id; any hit fails the run loudly and keeps the map file.
- **Obsidian rewrites files while the migration runs**: Mitigation: the command refuses to run when the vault has a lock the user names; the owner closes Obsidian first (hand-off step, not a code check).
- **Vault Templater templates still make local ids**: they live in the vault (`notes/system/templates/`), outside this repo. Out of scope; the owner updates them after PRD 00161 ships.
- **Not run on the real vault by this PRD**: the owner runs the dry run and the apply by hand after a backup.
