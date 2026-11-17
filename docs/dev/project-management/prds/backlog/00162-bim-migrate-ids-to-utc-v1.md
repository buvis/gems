---
default_model: opus
model_tier_rationale: destructive blast radius (renames notes and rewrites links across a vault) and an invented rewrite algorithm
lane: full
---

# bim: one-off script to migrate note ids to UTC

## Overview

### Problem Statement
Existing notes carry local-time ids (PRD 00161 switches new ids to UTC). The vault must move to one standard. Each note needs a new id, a new file name, and every reference to the old id updated. Some `date` fields have no time zone. The migration runs once, on one vault, so it is a standalone script kept in the repo spikes tree. It is not a bim command, so it adds no CLI surface, skill text, or CHANGELOG entry to maintain.

### Target Users
The vault owner, running the script once after a backup.

### Success Metrics
- After `migrate_ids.py --apply`, every note id equals the UTC digits of its `date`, or carries a seconds `60` to `99` collision suffix on those digits, or the note is listed as skipped with a reason.
- No wikilink, embed, or backmatter reference to an old id remains.
- `migrate_ids.py --undo MAPFILE` restores every file name, `id`, and `date` it changed.
- A dry run changes no file.

## Functional Decomposition

### Capability: Plan

#### Feature: Resolve the time zone
- **Description**: Decide the UTC instant of each note.
- **Inputs**: The `date` frontmatter value, the old id, and the option `--naive-timezone` (default `Europe/Prague`).
- **Outputs**: A timezone-aware date, and a flag `date_changed`.
- **Behavior**: A `date` with an offset keeps it. A `date` without an offset is read as local time of the `--naive-timezone` zone with DST through `zoneinfo`, and the offset is written into `date`. A local time that does not exist or repeats (DST change) is skipped and reported; the skipped note keeps its old id and file name, so links to it stay valid. A note without `date` takes the digits of its old id as local time of the same zone, and gets a `date` line with the offset.

#### Feature: Build the mapping
- **Description**: Map each old id to a new id.
- **Inputs**: The resolved dates and all `.md` notes under `<vault>/notes`.
- **Outputs**: A mapping `old id -> new id`, plus skipped notes with reasons.
- **Behavior**: New id = UTC digits (`%Y%m%d%H%M%S`). When two notes share a new id, or a new id is held by a note that is not itself being renamed, the later note (by old id) takes seconds `60`, `61`, up to `99`; after `99` the note is skipped and reported. A note whose new id equals its old id is left alone. The mapping may contain chains (a new id equals another note's old id) and cycles (two notes swap ids). The plan orders renames so none overwrites a file, and breaks a cycle through a temporary name.

### Capability: Apply and undo

#### Feature: Apply
- **Description**: Rewrite the vault from the mapping.
- **Inputs**: The mapping and `--apply`.
- **Outputs**: Renamed files, updated frontmatter, updated references, and a map file.
- **Behavior**: First write the map file (JSON, old and new id, old and new `date`, old and new file name, and a SHA-256 of each file after the change) to `~/.local/state/bim/migrate-ids/<UTC timestamp>.json`; abort if that path is inside the vault. Then rename each file with an atomic move and change the `id` and `date` frontmatter lines by editing those lines as text (never re-serialize the YAML, so every other byte stays). Rewrite references in one pass per file: a single regex over all old ids at once, so a link is never rewritten twice when a new id equals another note's old id. Reference forms in every `.md` file of the vault: `[[notes/<old>|...]]`, `[[notes/<old>]]`, `![[notes/<old>#...]]`, `[[<old>...]]` and Dataview `key:: [[...]]` values. Do not touch code fences or inline code. Stop at the first error and leave the map file in place. All writes go through `pybase.filesystem.atomic_write_text`.

#### Feature: Dry run and undo
- **Description**: Show the plan without writing; reverse an applied run.
- **Inputs**: `--vault PATH` (required), no other flag (dry run), `--apply`, or `--undo MAPFILE`.
- **Outputs**: A table of planned changes; or restored files.
- **Behavior**: The default is a dry run that prints the plan and the count of references to rewrite. `--apply` performs it. `--undo MAPFILE` applies the reverse mapping the same way, in one pass. A file whose hash differs from the map file's recorded hash was changed since the apply: it is skipped and reported, and its references are not rewritten.

## Structural Decomposition

### Repository Structure

```
docs/dev/project-management/spikes/bim-migrate-ids/
├── migrate_ids.py        # Maps to: Plan, Apply, Dry run and undo
└── test_migrate_ids.py   # Maps to: all features
```

### Module: migrate_ids
- **Maps to capability**: Plan; Apply and undo
- **Responsibility**: Compute the mapping, apply it, and undo it, from a command line. No import from `bim`, so the script does not depend on PRD 00161 code.
- **Exports**:
  - `plan_migration()` - build the mapping and the skip list.
  - `apply_migration()` - write the map file, rename, rewrite.
  - `undo_migration()` - reverse a map file.
- New symbols: `plan_migration`, `apply_migration`, `undo_migration`, `date_changed`, `zoneinfo`

### Module: tests
- **Maps to capability**: all
- **Responsibility**: One test per rule, in `docs/dev/project-management/spikes/bim-migrate-ids/test_migrate_ids.py`.
- New symbols: `prague_dst_summer_offset`, `prague_dst_winter_offset`, `aware_date_keeps_offset`, `ambiguous_dst_time_is_skipped`, `same_new_id_gets_suffix_60`, `apply_rewrites_all_reference_forms`, `code_fences_untouched`, `undo_restores_bytes`, `chain_and_swap_rename_safely`, `link_not_rewritten_twice`, `frontmatter_other_bytes_unchanged`, `dry_run_writes_nothing`, `script_help_lists_apply_and_undo`

## Dependency Graph

### Foundation Layer (Phase 0)
- **migrate_ids (plan)**: no dependency on code of PRD 00161; it applies the same UTC id rule, restated in this PRD.

### Core Layer (Phase 1)
- **migrate_ids (apply, undo)**: Depends on [migrate_ids (plan)]

### Integration Layer (Phase 2)
- **command line**: Depends on [migrate_ids (apply, undo)]

## Implementation Phases

### Phase 0: Plan
**Goal**: A dry-run plan is correct on a fixture vault.

**Tasks**:
- [ ] Write `plan_migration` (no deps) - Acceptance: tests `prague_dst_summer_offset`, `prague_dst_winter_offset`, `aware_date_keeps_offset`, `ambiguous_dst_time_is_skipped`, `same_new_id_gets_suffix_60` in `docs/dev/project-management/spikes/bim-migrate-ids/test_migrate_ids.py` pass.

**Exit Criteria**: Plan tests pass.

### Phase 1: Apply and undo
**Goal**: Apply and undo are lossless on a fixture vault.

**Tasks**:
- [ ] Write `apply_migration` and `undo_migration`. Premise: tests use a scratch fixture vault; at execution re-check that the vault path is the one given with `--vault` and that the map file path is outside it; a failed premise means abort, never force (depends on: Phase 0) - Acceptance: tests `apply_rewrites_all_reference_forms`, `code_fences_untouched`, `undo_restores_bytes` (compare a hash of every file before and after apply plus undo), `chain_and_swap_rename_safely`, `link_not_rewritten_twice`, `frontmatter_other_bytes_unchanged`, `dry_run_writes_nothing` pass.

**Exit Criteria**: Apply and undo tests pass.

### Phase 2: Command line
**Goal**: The script runs from a shell with a safe default.

**Tasks**:
- [ ] Add the `argparse` entry point with `--vault`, `--apply`, `--undo`, and `--naive-timezone` (depends on: Phase 1) - Acceptance: test `script_help_lists_apply_and_undo` runs `uv run python docs/dev/project-management/spikes/bim-migrate-ids/migrate_ids.py --help` and passes.

**Exit Criteria**: `uv run pytest docs/dev/project-management/spikes/bim-migrate-ids` passes. No `CHANGELOG.md` entry and no `SKILL.md` change: the script is not part of the product.

## Test Strategy

### Critical Scenarios
- **Happy path**: a vault with 3 notes, one with `+02:00`, one with `+01:00`, one naive; all get UTC ids and all links update.
- **Edge case**: two notes map to the same UTC second; the later one gets seconds `60`. Two notes whose new ids equal each other's old ids swap files and links correctly.
- **Error case**: a naive date inside the autumn DST overlap is skipped and listed; the apply stops on a write error and `undo` restores the already changed files.

## Risks

- **The vault is large and links come in many forms**: an unlisted form leaves a dead link. Mitigation: the apply ends with a scan for every old id; any hit fails the run loudly and keeps the map file.
- **Obsidian rewrites files while the script runs**: Mitigation: none in code. The hand-off tells the owner to close Obsidian and back up the vault first. The per-file hash check in undo detects files changed afterwards.
- **The script and PRD 00161 can disagree on the UTC rule**: both restate it (UTC digits of `date`, suffix `60` to `99`). Mitigation: a Phase 0 test fixes the expected ids, and a mismatch is reported at review.
- **Obsidian Templater**: already solved. The vault templates write UTC ids since 2026-11-17, so notes made after that date need no migration (they already match the UTC rule). The script still processes them and leaves them unchanged. It must not change the templates.
- **Not run on the real vault by this PRD**: the owner runs the dry run and the apply by hand after a backup.
