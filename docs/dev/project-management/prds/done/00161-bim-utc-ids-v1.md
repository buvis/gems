---
default_model: opus
model_tier_rationale: Rust and Python must give identical ids, and the tasks rewrite existing tests that pin local-time ids
---

# bim: UTC note ids with collision suffix

## Overview

### Problem Statement
A bim note id is the local wall-clock digits of its `date` (`YYYYMMDDHHMMSS`). When the user travels west, the local clock goes back. A note created later can then get an id that an older note already holds. `bim create` never overwrites: it reserves the file with `O_EXCL` and makes up to 5 attempts with a 1-second sleep between them (`MAX_ID_ATTEMPTS` in `CreateZettelUseCase`). It then fails with `FileExistsError`. So the harm today is a failed or delayed create and ids that do not sort by creation time. Ids must not depend on the time zone. This PRD reverses the local-time id rule of PRD 00118, because the vault templates now write UTC ids.

### Target Users
The vault owner, who travels between time zones, and agents that call `bim create`.

### Success Metrics
- The id of a new note equals the UTC digits of its `date`, for any local offset.
- Two notes created in the same UTC second get ids with seconds `60`, `61`, up to `99`.
- No `time.sleep` runs on an id collision.
- When the base id and all of `60` to `99` are taken, the create fails with an explicit error. No file is overwritten.

## Functional Decomposition

### Capability: UTC id derivation

#### Feature: UTC id from date
- **Description**: The default id is the UTC digits of the note date.
- **Inputs**: `metadata["date"]`, a `datetime`.
- **Outputs**: `metadata["id"]` as an `int` of 14 digits.
- **Behavior**: For a timezone-aware `date`: `int(date.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"))`. A naive `date` is read as UTC, so its digits are used unchanged: `int(date.strftime("%Y%m%d%H%M%S"))`. Do not call `astimezone` on a naive value (Python would read it as system local time). This matches the Rust parser, which labels a naive frontmatter date as UTC (`src/rust/src/types.rs`, the `NaiveDateTime` branch). There is no time-zone setting. PRD 00162 decides the zone of old naive dates and writes the offset into `date`.

#### Feature: Date from id
- **Description**: A note file without frontmatter date takes its date from the id in the file name.
- **Inputs**: A file stem that starts with 12 or 14 digits.
- **Outputs**: A timezone-aware `datetime` in UTC.
- **Behavior**: Parse as UTC, not local. Seconds `60` to `99` map to second `59` of the same minute, because the suffix is a collision counter and not a time.

#### Feature: Rust mirror
- **Description**: The Rust core duplicates both rules above and must give identical results (`tests/lib/zettel/parity/test_rust_python_parity.py`). Production reads go through Rust, so this is the path that users see.
- **Inputs**: `src/rust/src/consistency/defaults.rs` (private `set_default_id`, today the date's own wall clock) and `src/rust/src/parser/enrichment.rs` (`date_from_filename`, today `Local`).
- **Outputs**: UTC id; UTC date from a file name; seconds `60` to `99` map to `59`.
- **Behavior**: Same rules as the Python features. Format the id from `date.with_timezone(&Utc)`. In `date_from_filename`, change seconds `60` to `99` to `59` before the chrono parse: chrono accepts `60` as a leap second and rejects `61` to `99`. Increment `CACHE_VERSION` in `src/rust/src/scanner.rs`, because cached metadata holds ids and dates made with the old rules.

### Capability: Collision suffix

#### Feature: Seconds-slot suffix
- **Description**: When the id file exists, the seconds field takes `60`, `61`, up to `99`.
- **Inputs**: The UTC base id and the target path.
- **Outputs**: A free id, or an error.
- **Behavior**: Try the base id. On collision try `base[:12] + "60"`, then `"61"`, up to `"99"`. After `"99"` raise `FileExistsError` naming the path. Do not sleep. Keep the `O_EXCL` reservation: a reservation that fails with `FileExistsError` (another writer took the path first) is a collision and takes the next candidate. Remove `MAX_ID_ATTEMPTS`, the `time.sleep(1)` calls and `import time`. The `slug`-stem templates (contact, book) keep their fail-fast behavior. The note's `date` is not changed: a suffixed note has an id that differs from the digits of its `date`, by design.

### Capability: Documentation

#### Feature: Docs describe UTC ids
- **Description**: Every user-facing text that states the local-time id rule states the new rule.
- **Inputs**: `src/tools/bim/SKILL.md` (line "Ids equal the local-time digits of `date`"), `README.md` (sentence "Ids follow local time like the vault's own notes"), `docs/source/tools/bim.rst` (paragraph "Ids follow local time ... the second waits for the next free id").
- **Outputs**: The three texts say: the id is the UTC digits of `date`; seconds `60` to `99` mark same-second collisions; a create never waits.
- **Behavior**: Also correct the code comments that state the old rule in `defaults.rs`, `enrichment.rs` and `zettel_file_parser.py`. Add one `CHANGELOG.md` line under `### Changed` in `[Unreleased]`, prefixed `**bim**:`.

## Structural Decomposition

### Repository Structure

```
src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py                # Maps to: UTC id from date
src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py                # Maps to: Seconds-slot suffix
src/lib/buvis/pybase/zettel/infrastructure/persistence/file_parsers/zettel_file_parser.py  # Maps to: Date from id
src/rust/src/consistency/defaults.rs                        # Maps to: Rust mirror (id)
src/rust/src/parser/enrichment.rs                           # Maps to: Rust mirror (date from file name)
src/rust/src/scanner.rs                                     # Maps to: Rust mirror (cache version)
src/tools/bim/SKILL.md                                      # Maps to: Docs describe UTC ids
README.md                                                   # Maps to: Docs describe UTC ids
docs/source/tools/bim.rst                                   # Maps to: Docs describe UTC ids
CHANGELOG.md                                                # Maps to: Docs describe UTC ids
tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py
tests/lib/zettel/application/test_create_zettel_use_case.py
tests/lib/zettel/infrastructure/test_zettel_file_parser.py
tests/lib/zettel/parity/test_rust_python_parity.py
tests/tools/bim/test_create_note_vault.py
```

### Module: set_default_id
- **Maps to capability**: UTC id derivation
- **Responsibility**: Derive the id from the date in UTC.
- **Exports**: `set_default_id()` - sets `metadata["id"]`.

### Module: zettel_file_parser
- **Maps to capability**: UTC id derivation
- **Responsibility**: Read the date from a file name as UTC.
- **Exports**: `_get_date_from_file()`.

### Module: rust core
- **Maps to capability**: UTC id derivation (Rust mirror)
- **Responsibility**: Same UTC id and file-name date rules as Python.
- **Exports**: none new. `set_default_id` (defaults.rs) is internal; `date_from_filename` (enrichment.rs) keeps its signature.

### Module: CreateZettelUseCase
- **Maps to capability**: Collision suffix
- **Responsibility**: Reserve a free id path without sleeping.
- **Exports**: `CreateZettelUseCase.prepare()`, `CreateZettelUseCase.execute()`.
- New symbols: `_suffixed_id`

### Module: tests
- **Maps to capability**: all
- **Responsibility**: One test per rule, in the five test files listed above. Each name below is a pytest function `test_<name>`.
- New symbols: `utc_id_ignores_local_offset`, `naive_date_keeps_its_digits`, `file_name_date_is_utc`, `suffix_seconds_map_to_59`, `same_second_gets_suffix_60`, `suffix_runs_to_99`, `collision_after_99_raises`, `lost_reservation_takes_next_suffix`, `create_never_sleeps`, `rust_python_id_parity_utc`, `rust_filename_date_utc`

### Module: docs
- **Maps to capability**: Documentation
- **Responsibility**: State the UTC id rule and the collision suffix.
- **Exports**: none.

## Dependency Graph

### Foundation Layer (Phase 0)
- **set_default_id**: no dependencies; built first.
- **zettel_file_parser**: no dependencies.
- **rust core**: no dependencies; must match set_default_id and zettel_file_parser.

### Core Layer (Phase 1)
- **CreateZettelUseCase**: Depends on [set_default_id]

### Integration Layer (Phase 2)
- **docs**: Depends on [set_default_id, CreateZettelUseCase]

## Implementation Phases

Premise for every task that rewrites tests: the named existing tests pin the old local-time rule and must change with the code. Re-check at execution that each named test exists. If one does not, read the file again before you edit. Never delete a test that this PRD does not name.

### Phase 0: Foundation
**Goal**: Ids and file-name dates use UTC.

**Tasks**:
- [ ] Change `set_default_id` to use UTC (no deps). Replace the existing parametrized test `test_sets_id_from_dates_own_wall_clock` in `tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py`. In `tests/tools/bim/test_create_note_vault.py`, change the assertion `f"{local:%Y%m%d%H%M%S}" == str(saved.id)` to compare with the UTC digits of the saved `date` - Acceptance: new tests `utc_id_ignores_local_offset` (`2024-09-13T12:00:00+02:00` gives `20240913100000`) and `naive_date_keeps_its_digits` pass, and `uv run pytest tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py tests/tools/bim/test_create_note_vault.py` passes.
- [ ] Change `_get_date_from_file` to parse the digits as UTC and to map seconds 60-99 to 59 (no deps). Replace `test_14_digit_filename_is_local_wall_clock` and `test_12_digit_filename_is_local_wall_clock` in `tests/lib/zettel/infrastructure/test_zettel_file_parser.py` - Acceptance: new tests `file_name_date_is_utc` (14 and 12 digits) and `suffix_seconds_map_to_59` pass, and `uv run pytest tests/lib/zettel/infrastructure/test_zettel_file_parser.py` passes.
- [ ] Mirror both rules in Rust as the Rust mirror feature says (`defaults.rs`, `enrichment.rs`, `scanner.rs`) (no deps). Rewrite the Rust unit tests `test_id_keeps_the_dates_own_offset`, `test_default_date_is_local_time_without_subseconds` (the id part) and `test_filename_digits_are_local_wall_clock` to the UTC rules. Replace the parity test `test_default_id_follows_the_dates_own_offset_in_both_paths`. If a parity test named test_id_cut_from_the_file_creation_time_is_local_wall_clock exists (it arrives with the branch feature/config-local-layer-braid), change it to expect the UTC digits of the date. Rebuild the extension with maturin and sign the `.so` ad hoc on macOS; point the environment variables CARGO_HOME and CARGO_TARGET_DIR at a writable scratch directory - Acceptance: new tests `rust_python_id_parity_utc` and `rust_filename_date_utc` pass, `uv run pytest tests/lib/zettel/parity/test_rust_python_parity.py` passes, and `cargo test` in `src/rust` passes.

**Exit Criteria**: The test files above pass, and `cargo test` passes.

### Phase 1: Core
**Goal**: Same-second creates get suffixed ids and never sleep.

**Tasks**:
- [ ] Replace the retry loop and `time.sleep(1)` in `_prepare` and `execute` with `_suffixed_id` candidates `60` to `99` (depends on: Phase 0). Premise: the `O_EXCL` open in `execute` stays and still guards against a race; re-check at execution that it exists, and keep it. In `tests/lib/zettel/application/test_create_zettel_use_case.py`, replace `test_raises_file_exists` and all five tests of `TestCollisionBudget` (`test_waits_for_next_second_on_collision`, `test_gives_up_after_five_attempts`, `test_attempt_budget_resets_for_each_invocation`, `test_second_writer_loses_reservation_and_retries`, `test_existence_and_reservation_collisions_share_five_attempts`) with the new tests. Keep `test_slug_collision_fails_without_retry` unchanged - Acceptance: new tests `same_second_gets_suffix_60`, `suffix_runs_to_99`, `collision_after_99_raises` (base and `60` to `99` exist), `lost_reservation_takes_next_suffix`, `create_never_sleeps` pass, `uv run pytest tests/lib/zettel/application/test_create_zettel_use_case.py` passes, and `rg -c "MAX_ID_ATTEMPTS|time\.sleep" src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py` prints nothing.

**Exit Criteria**: The use-case test file passes.

### Phase 2: Integration
**Goal**: Docs match behavior and the full gate is green.

**Tasks**:
- [ ] Rewrite the id rule in `src/tools/bim/SKILL.md`, `README.md` and `docs/source/tools/bim.rst`, and correct the stale code comments (depends on: Phase 1) - Acceptance: `rg -c "UTC digits" src/tools/bim/SKILL.md README.md docs/source/tools/bim.rst` prints a count for each of the three files, and `rg -c "local-time digits|Ids follow local time|waits for the next free id" src/tools/bim/SKILL.md README.md docs/source/tools/bim.rst` prints nothing.
- [ ] Add the `CHANGELOG.md` line under `### Changed` in `[Unreleased]` (depends on: Phase 1) - Acceptance: `rg -n "\*\*bim\*\*.*UTC" CHANGELOG.md` prints the new line.

**Exit Criteria**: `uv run pytest tests/lib/zettel tests/tools/bim`, `cargo test` in `src/rust` and `uv run sphinx-build -b html docs/source docs/build/html` pass.

## Test Strategy

### Critical Scenarios
- **Happy path**: date `2026-11-17T08:37:39+01:00` → id `20261117073739`.
- **Edge case**: date `2026-11-17T01:30:00-06:00` and `2026-11-17T08:30:00+01:00` give the same base id and so the second gets suffix `60`.
- **Edge case**: naive date `2026-11-17 08:37:39` → id `20261117083739` in Python and in Rust.
- **Error case**: with the base id taken, 40 more creates succeed with `60` to `99`; the next create raises `FileExistsError`; no existing file changes.

## Risks

- **Seconds 60-99 break strict parsers**: `strptime` rejects them, and chrono rejects `61` to `99`. Mitigation: the Python and Rust file-name parsers map them to 59. Other id code is unchanged and never receives a suffix: `bim doc` builds its own timestamps (`commands/doc/shared/naming.py`, `pipeline.py`) and its files are not named `<id>.md`; `bim import` changes a colliding id as an integer (`src/tools/bim/shared/import_helpers.py`); klyreon and zseq are other tools.
- **Legacy notes without `date` change meaning at once**: after this PRD, `_get_date_from_file` reads their file-name digits as UTC, but until PRD 00162 runs those digits are local time. Mitigation: the window is short and affects only notes with no `date`; PRD 00162 resolves such notes (it reads their old id as local time) before the parser matters. `bim doc` zettels have no `date` either; their derived date moves by the local offset and nothing else uses it.
- **Mixed local and UTC ids until the migration (PRD 00162) runs**: an old local id can equal a new UTC id. Mitigation: the suffix check covers it; no overwrite is possible because of `O_EXCL`.
- **Naive dates**: a naive `date` gives an id that is off by the local offset, the same as today in both code paths. PRD 00162 writes the offset into old naive dates.
- **Obsidian Templater**: already solved. The vault templates in `notes/system/templates/` write UTC ids since 2026-11-17 (`moment.utc().format("YYYYMMDDHHmmss")`, verified by a note made from a template). Out of scope here; no task touches them.
