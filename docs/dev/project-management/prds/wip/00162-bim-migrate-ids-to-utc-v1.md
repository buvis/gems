---
default_model: opus
model_tier_rationale: destructive blast radius (renames notes and rewrites links across a vault) and an invented rewrite algorithm
lane: full
---

# bim: one-off script to migrate note ids to UTC

## Overview

### Problem Statement
Existing notes carry local-time ids (PRD 00161 switches new ids to UTC). The vault must move to one standard. Each note needs a new id, a new file name when the file is named after the id, and every link to the old file name updated. Some `date` fields have no time zone. The migration runs once, on one vault, so it is a standalone script kept in the repo spikes tree. It is not a bim command, so it adds no CLI surface, skill text, or CHANGELOG entry to maintain.

### Target Users
The vault owner, running the script once after a backup.

### Success Metrics
- After `migrate_ids.py --apply`, every migrated note id equals the UTC digits of its `date`, or carries a seconds `60` to `99` collision suffix on those digits, or the note is listed as skipped with a reason.
- No wikilink, embed, or backmatter reference to the old file name of a renamed note remains.
- `migrate_ids.py --undo MAPFILE` restores every byte and every file name it changed.
- A dry run changes no file.

## Functional Decomposition

### Capability: Plan

#### Feature: Select the notes
- **Description**: Decide which files are notes to migrate.
- **Inputs**: All `.md` files under `<vault>/notes`, read as bytes.
- **Outputs**: The notes to migrate; the files that are only scanned for references.
- **Behavior**: A note is a file whose frontmatter has an `id` line of 12 or 14 digits. A file without such a line (daily notes, boards, `index.md`) is not a note: it gets no mapping entry, but references in it are rewritten. A file whose frontmatter has `type: document` is a `bim doc` zettel: its id is already UTC or `<document date>000000`, and its file name is tied to a PDF and to the doc state database. It is never renamed and its id never changes; references in it are rewritten. Notes outside the vault (the bim archive) are not migrated.

#### Feature: Resolve the time zone
- **Description**: Decide the UTC instant of each note.
- **Inputs**: The `date` frontmatter value, the old id, and the option `--naive-timezone` (default `Europe/Prague`).
- **Outputs**: A timezone-aware date, and a flag `date_changed`.
- **Behavior**: A `date` with an offset keeps it. A `date` without an offset is read as local time of the `--naive-timezone` zone with DST through `zoneinfo`, and the offset is written into `date`. A local time that does not exist or repeats (DST change) is skipped and reported; `zoneinfo` raises no error for these, so compare the offsets for `fold=0` and `fold=1` and do a UTC round trip. A `date` that has no time (date only) or cannot be parsed is skipped and reported. A note without `date` takes the digits of its old id as local time of the same zone (a 12-digit id has seconds `00`), and gets a `date` line with the offset; an old id that is not a valid time is skipped and reported. A skipped note keeps its old id and file name, so links to it stay valid.

#### Feature: Build the mapping
- **Description**: Map each old id to a new id, and each old file stem to a new file stem.
- **Inputs**: The resolved dates and the selected notes.
- **Outputs**: A mapping `old id -> new id` and `old stem -> new stem`, plus skipped notes with reasons.
- **Behavior**: New id = UTC digits (`%Y%m%d%H%M%S`). When two notes share a new id, or a new id is held by a note that is not itself being renamed, the later note (by old id) takes seconds `60`, `61`, up to `99`; after `99` the note is skipped and reported. A note whose new id equals its old id is left alone. Rename a file only when its stem starts with the old id and the next character is not a digit (`<id>.md`, `<id>_a.md`): replace that prefix with the new id. When the stem is not the id (`contact/<slug>.md`, `book/<slug>.md`, `<slug>.hub.md`), change only the `id` line and keep the file name. Files named after the id that are not notes (`<id>.svg` beside an illustrated note, the project resources folder outside the vault) keep their names, and the Markdown links to them (`![..](<id>.svg)`, `file://` links) are not changed, so they stay valid. The mapping may contain chains (a new stem equals another note's old stem) and cycles (two notes swap stems). The plan orders renames so none overwrites a file, and breaks a cycle through a temporary name.

### Capability: Apply and undo

#### Feature: Apply
- **Description**: Rewrite the vault from the mapping.
- **Inputs**: The mapping, `--apply`, and the map directory.
- **Outputs**: Renamed files, updated frontmatter, updated references, and a map file.
- **Behavior**: Compute the new bytes of every file in memory first. Then write the map file (JSON: old and new id, old and new `date` line, old and new path, and a SHA-256 of each file before and after the change) to `<map dir>/<UTC timestamp>.json`; abort if that path is inside the vault. The map directory is a function parameter; the command-line default is `$XDG_STATE_HOME/bim/migrate-ids`, with `~/.local/state` when the variable is not set. Then rename each file with an atomic move and change the `id` and `date` frontmatter lines by editing those lines as bytes (never re-serialize the YAML and never decode with newline translation, so every other byte stays). Rewrite references in one pass per file: a single regex over all old stems at once, longest first, so a link is never rewritten twice when a new stem equals another note's old stem. A reference is a wikilink or embed (`[[...]]`, `![[...]]`, also as a Dataview `key:: [[...]]` value) whose target, before `|`, `#` or `]]`, ends with an old stem that follows `[[` or `/`: `[[<old>]]`, `[[notes/<old>|...]]`, `[[notes/<folder>/<old>#...]]`. A digit string inside a longer digit string, in plain text or in a Markdown link is not a reference. Do not touch code fences or inline code. After the rewrite, scan every `.md` file for references to an old stem that is not also a new stem; any hit fails the run and keeps the map file. Stop at the first error and leave the map file in place. All writes go through `buvis.pybase.filesystem.atomic_write_bytes`.

#### Feature: Dry run and undo
- **Description**: Show the plan without writing; reverse an applied run.
- **Inputs**: `--vault PATH` (required), no other flag (dry run), `--apply`, or `--undo MAPFILE`.
- **Outputs**: A table of planned changes; or restored files.
- **Behavior**: The default is a dry run. It prints the plan and these counts: notes to migrate, notes already on UTC, skipped notes by reason, notes whose old id differs from the local digits of `date`, references to rewrite, and id-named attachments that keep their names. `--apply` performs it. `--undo MAPFILE` applies the reverse mapping the same way, in one pass. Undo decides per file from the recorded hashes: a file at its new path with the after hash is restored; a file at its old path with the before hash was never changed and is left alone (this is the state after a stopped apply); any other file was changed since the apply, so it is skipped and reported, and its references are not rewritten.

## Structural Decomposition

### Repository Structure

```
docs/dev/project-management/spikes/bim-migrate-ids/
├── migrate_ids.py        # Maps to: Plan, Apply, Dry run and undo
└── test_migrate_ids.py   # Maps to: all features
```

### Module: migrate_ids
- **Maps to capability**: Plan; Apply and undo
- **Responsibility**: Compute the mapping, apply it, and undo it, from a command line. No import from `bim`, so the script does not depend on PRD 00161 code. It may import `buvis.pybase.filesystem`.
- **Exports**:
  - `plan_migration()` - select the notes, build the mapping and the skip list.
  - `apply_migration()` - write the map file, rename, rewrite, scan.
  - `undo_migration()` - reverse a map file.
- New symbols: `plan_migration`, `apply_migration`, `undo_migration`, `date_changed`, `zoneinfo`

### Module: tests
- **Maps to capability**: all
- **Responsibility**: One test per rule, in `docs/dev/project-management/spikes/bim-migrate-ids/test_migrate_ids.py`. Each name below is a pytest function `test_<name>`. The test file loads `migrate_ids.py` with `importlib.util.spec_from_file_location`, as `tests/dev/test_scaffold.py` does, because pytest runs in importlib mode and the script directory is not on `sys.path`. Every test uses a fixture vault and a map directory under `tmp_path`; no test writes to the real home.
- New symbols: `prague_dst_summer_offset`, `prague_dst_winter_offset`, `aware_date_keeps_offset`, `ambiguous_dst_time_is_skipped`, `nonexistent_dst_time_is_skipped`, `date_only_is_skipped`, `note_without_date_uses_old_id`, `document_zettel_is_not_migrated`, `slug_named_note_keeps_file_name`, `file_without_id_is_not_a_note`, `same_new_id_gets_suffix_60`, `apply_rewrites_all_reference_forms`, `longer_digit_string_is_not_a_reference`, `attachment_links_untouched`, `code_fences_untouched`, `leftover_reference_fails_apply`, `undo_restores_bytes`, `stopped_apply_then_undo_restores_bytes`, `chain_and_swap_rename_safely`, `link_not_rewritten_twice`, `frontmatter_other_bytes_unchanged`, `dry_run_writes_nothing`, `script_help_lists_apply_and_undo`

## Dependency Graph

### Foundation Layer (Phase 0)
- **migrate_ids (plan)**: no dependency on code of PRD 00161; it applies the same UTC id rule, restated in this PRD.

### Core Layer (Phase 1)
- **migrate_ids (apply, undo)**: Depends on [migrate_ids (plan)]

### Integration Layer (Phase 2)
- **migrate_ids (command line)**: Depends on [migrate_ids (apply, undo)]

## Implementation Phases

### Phase 0: Foundation
**Goal**: A dry-run plan is correct on a fixture vault.

**Tasks**:
- [ ] Write `plan_migration` (no deps) - Acceptance: tests `prague_dst_summer_offset`, `prague_dst_winter_offset`, `aware_date_keeps_offset`, `ambiguous_dst_time_is_skipped`, `nonexistent_dst_time_is_skipped`, `date_only_is_skipped`, `note_without_date_uses_old_id`, `document_zettel_is_not_migrated`, `slug_named_note_keeps_file_name`, `file_without_id_is_not_a_note`, `same_new_id_gets_suffix_60` in `docs/dev/project-management/spikes/bim-migrate-ids/test_migrate_ids.py` pass.

**Exit Criteria**: Plan tests pass.

### Phase 1: Core
**Goal**: Apply and undo are lossless on a fixture vault.

**Tasks**:
- [ ] Write `apply_migration` and `undo_migration`. Premise: tests use a scratch fixture vault; at execution re-check that the vault path is the one given with `--vault` and that the map file path is outside it; a failed premise means abort, never force (depends on: Phase 0) - Acceptance: tests `apply_rewrites_all_reference_forms`, `longer_digit_string_is_not_a_reference`, `attachment_links_untouched`, `code_fences_untouched`, `leftover_reference_fails_apply`, `undo_restores_bytes` (compare a hash of every file before and after apply plus undo, with one CRLF file in the fixture), `stopped_apply_then_undo_restores_bytes` (a write error after some files, then undo), `chain_and_swap_rename_safely`, `link_not_rewritten_twice`, `frontmatter_other_bytes_unchanged`, `dry_run_writes_nothing` pass.

**Exit Criteria**: Apply and undo tests pass.

### Phase 2: Integration
**Goal**: The script runs from a shell with a safe default.

**Tasks**:
- [ ] Add the `argparse` entry point with `--vault`, `--apply`, `--undo`, and `--naive-timezone` (depends on: Phase 1) - Acceptance: test `script_help_lists_apply_and_undo` runs `[sys.executable, "docs/dev/project-management/spikes/bim-migrate-ids/migrate_ids.py", "--help"]` and passes.

**Exit Criteria**: `uv run pytest docs/dev/project-management/spikes/bim-migrate-ids` passes. This command is the only gate: ruff, mypy and CI do not cover the spikes tree. No `CHANGELOG.md` entry and no `SKILL.md` change: the script is not part of the product.

## Test Strategy

### Critical Scenarios
- **Happy path**: a vault with 3 notes, one with `+02:00`, one with `+01:00`, one naive; all get UTC ids and all links update.
- **Edge case**: two notes map to the same UTC second; the later one gets seconds `60`. Two notes whose new stems equal each other's old stems swap files and links correctly.
- **Edge case**: a `type: document` zettel, a `contact/<slug>.md` note and a daily note without `id` keep their file names; only the contact note gets a new `id` line.
- **Error case**: a naive date inside the autumn DST overlap is skipped and listed; the apply stops on a write error and `undo` restores the already changed files.

## Risks

- **The vault is large and links come in many forms**: an unlisted form leaves a dead link. Mitigation: the scan at the end of the apply fails the run loudly and keeps the map file.
- **Obsidian rewrites files while the script runs**: Mitigation: none in code. The hand-off tells the owner to close Obsidian and back up the vault first. The per-file hash check in undo detects files changed afterwards.
- **Stale caches and stores after renames**: the zettel metadata cache `~/.cache/buvis/zettel_cache.bin` is keyed by file path. Mitigation: the hand-off tells the owner to delete it after an apply and after an undo.
- **A note saved by bim in the past can have a wrong offset**: the Rust parser read a naive `date` as UTC and bim then wrote it with the local offset. For such a note the script sees an id that already equals the UTC digits and leaves it alone. Mitigation: the dry run prints the count of notes whose old id differs from the local digits of `date`, so the owner can inspect them first.
- **The script and PRD 00161 can disagree on the UTC rule**: both restate it (UTC digits of `date`, suffix `60` to `99`). Mitigation: a Phase 0 test fixes the expected ids, and a mismatch is reported at review.
- **Obsidian Templater**: already solved. The vault templates write UTC ids since 2026-11-17, so notes made after that date need no migration (they already match the UTC rule). The script still processes them and leaves them unchanged. It must not change the templates.
- **Not run on the real vault by this PRD**: the owner runs the dry run and the apply by hand after a backup.
