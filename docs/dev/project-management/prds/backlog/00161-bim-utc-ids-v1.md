---
default_model: sonnet
model_tier_rationale: exact expressions given for id and suffix; additive tests that fail loudly
---

# bim: UTC note ids with collision suffix

## Overview

### Problem Statement
A bim note id is the local wall-clock digits of its `date` (`YYYYMMDDHHMMSS`). When the user travels west, the local clock goes back. A note created later can then get an id that an older note already holds. `bim create` never overwrites: it reserves the file with `O_EXCL` and retries up to 5 times with a 1-second sleep (`CreateZettelUseCase.execute`). It then fails with `FileExistsError`. So the harm today is a failed or delayed create and ids that do not sort by creation time. Other id writers (Obsidian Templater, `bim doc`, `bim import`) have their own collision handling. Ids must not depend on the time zone.

### Target Users
The vault owner, who travels between time zones, and agents that call `bim create`.

### Success Metrics
- The id of a new note equals the UTC digits of its `date`, for any local offset.
- Two notes created in the same UTC second get ids with seconds `60`, `61`, up to `99`.
- No `time.sleep` runs on an id collision.
- Collision 100 in the same second fails with an explicit error. No file is overwritten.

## Functional Decomposition

### Capability: UTC id derivation

#### Feature: UTC id from date
- **Description**: The default id is the UTC digits of the note date.
- **Inputs**: `metadata["date"]`, a timezone-aware `datetime`.
- **Outputs**: `metadata["id"]` as an `int` of 14 digits.
- **Behavior**: `int(date.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"))`. A naive `date` is treated as `Europe/Prague` local time (the vault owner's zone), DST-aware (guess).

#### Feature: Date from id
- **Description**: A note file without frontmatter date takes its date from the id in the file name.
- **Inputs**: A file stem that starts with 12 or 14 digits.
- **Outputs**: A timezone-aware `datetime` in UTC.
- **Behavior**: Parse as UTC, not local. Seconds `60` to `99` fall back to second `59` of the same minute (guess), because the suffix is a collision counter and not a time.

### Capability: Collision suffix

#### Feature: Seconds-slot suffix
- **Description**: When the id file exists, the seconds field takes `60`, `61`, up to `99`.
- **Inputs**: The UTC base id and the target path.
- **Outputs**: A free id, or an error.
- **Behavior**: Try the base id. On collision try `base[:12] + "60"`, then `"61"`, up to `"99"`. After `"99"` raise `FileExistsError` naming the path. Do not sleep. Keep the `O_EXCL` reservation. The `slug`-stem templates (contact, book) keep their fail-fast behavior.

### Capability: Skill text

#### Feature: Skill describes UTC ids
- **Description**: `bim --skill` states the new id rule.
- **Inputs**: `src/tools/bim/SKILL.md`.
- **Outputs**: The line "Ids equal the local-time digits of `date`" is replaced.
- **Behavior**: State that the id is the UTC digits of `date`, and that seconds `60` to `99` mark same-second collisions.

## Structural Decomposition

### Repository Structure

```
src/lib/buvis/pybase/zettel/
├── domain/entities/zettel/fixers/set_default_id.py        # Maps to: UTC id from date
├── application/use_cases/create_zettel_use_case.py        # Maps to: Seconds-slot suffix
└── infrastructure/persistence/file_parsers/zettel_file_parser.py  # Maps to: Date from id
src/tools/bim/SKILL.md                                      # Maps to: Skill describes UTC ids
tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py
tests/lib/zettel/application/test_create_zettel_use_case.py
tests/lib/zettel/infrastructure/test_zettel_file_parser.py
```

### Module: set_default_id
- **Maps to capability**: UTC id derivation
- **Responsibility**: Derive the id from the date in UTC.
- **Exports**: `set_default_id()` - sets `metadata["id"]`.

### Module: CreateZettelUseCase
- **Maps to capability**: Collision suffix
- **Responsibility**: Reserve a free id path without sleeping.
- **Exports**: `CreateZettelUseCase.prepare()`, `CreateZettelUseCase.execute()`.
- New symbols: `_suffixed_id`

### Module: tests
- **Maps to capability**: all
- **Responsibility**: One test per rule, in the three test files listed above.
- New symbols: `utc_id_ignores_local_offset`, `naive_date_treated_as_prague`, `file_name_date_is_utc`, `suffix_seconds_map_to_59`, `same_second_gets_suffix_60`, `suffix_runs_to_99`, `collision_after_99_raises`, `create_never_sleeps`

### Module: zettel_file_parser
- **Maps to capability**: UTC id derivation
- **Responsibility**: Read the date from a file name as UTC.
- **Exports**: `_get_date_from_file()`.

## Dependency Graph

### Foundation Layer (Phase 0)
- **set_default_id**: no dependencies; built first.
- **zettel_file_parser**: no dependencies.

### Core Layer (Phase 1)
- **CreateZettelUseCase**: Depends on [set_default_id]

### Integration Layer (Phase 2)
- **SKILL.md**: Depends on [set_default_id, CreateZettelUseCase]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Ids and file-name dates use UTC.

**Tasks**:
- [ ] Change `set_default_id` to use UTC (no deps) - Acceptance: new tests `utc_id_ignores_local_offset` and `naive_date_treated_as_prague` in `tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py` pass.
- [ ] Change `_get_date_from_file` to parse the digits as UTC and to map seconds 60-99 to 59 (no deps) - Acceptance: new tests `file_name_date_is_utc` and `suffix_seconds_map_to_59` in `tests/lib/zettel/infrastructure/test_zettel_file_parser.py` pass.

**Exit Criteria**: Both test files pass.

### Phase 1: Core
**Goal**: Same-second creates get suffixed ids and never sleep.

**Tasks**:
- [ ] Replace the retry loop and `time.sleep(1)` in `_prepare` and `execute` with `_suffixed_id` candidates `60` to `99` (depends on: Phase 0). Premise: the `O_EXCL` open in `execute` stays and still guards against a race; re-check at execution that it exists, and keep it. - Acceptance: new tests `same_second_gets_suffix_60`, `suffix_runs_to_99`, `collision_after_99_raises`, `create_never_sleeps` (patch `time.sleep` to fail) in `tests/lib/zettel/application/test_create_zettel_use_case.py` pass.

**Exit Criteria**: The use-case test file passes.

### Phase 2: Integration
**Goal**: Docs match behavior and the full gate is green.

**Tasks**:
- [ ] Rewrite the SKILL.md id line (depends on: Phase 1) - Acceptance: `rg -c "UTC digits" src/tools/bim/SKILL.md` prints `1` or more and `rg -c "local-time digits" src/tools/bim/SKILL.md` prints `0`.
- [ ] Add a `CHANGELOG.md` entry under Fixed or Changed for bim (depends on: Phase 1) - Acceptance: `rg -c "UTC" CHANGELOG.md` prints `1` or more.

**Exit Criteria**: The project test gate passes (`uv run pytest tests/lib/zettel tests/tools/bim`).

## Test Strategy

### Critical Scenarios
- **Happy path**: date `2026-11-17T08:37:39+01:00` → id `20261117073739`.
- **Edge case**: date `2026-11-17T01:30:00-06:00` and `2026-11-17T08:30:00+01:00` give the same base id and so the second gets suffix `60`.
- **Error case**: 40 same-second creates succeed with `60` to `99`; the 41st raises `FileExistsError`; no existing file changes.

## Risks

- **Seconds 60-99 break strict parsers**: `strptime` rejects them. Mitigation: the file-name parser maps them to 59; the Rust `_core` parser must be checked at execution (premise: `rg -n "strptime|chrono" src/lib` for the Rust side); a failed premise is reported, not forced.
- **Mixed local and UTC ids until the migration (PRD 00162) runs**: an old local id can equal a new UTC id. Mitigation: the suffix check covers it; no overwrite is possible because of `O_EXCL`.
- **Obsidian Templater still writes local ids**: out of scope here; PRD 00162 covers the vault templates.
