# Design: 00161 bim UTC note ids with collision suffix

## Architecture fit

- Zettel domain layer: the `set_default_id` fixer (`domain/entities/zettel/fixers/`) runs inside `ZettelConsistencyService` for every Python-built note, including `bim create` (via `ZettelFactory.create`).
- Zettel infrastructure layer: `_get_date_from_file` in `zettel_file_parser.py` is the Python read path when frontmatter has no `date`.
- Zettel application layer: `CreateZettelUseCase` owns id allocation and the `O_EXCL` reservation. All interfaces (CLI `bim create`, `--json`, TUI, WebUI) reach it through `bim/commands/create_note/create_note.py` (`prepare` for dry run, `execute` for real), so one change covers all interfaces.
- Rust core (`src/rust/src`): production reads go through it. `consistency/defaults.rs::set_default_id` mirrors the Python fixer; `parser/enrichment.rs::date_from_filename` mirrors `_get_date_from_file`; `scanner.rs::CACHE_VERSION` invalidates cached metadata.
- Layering holds: no new imports across layers; the library stays interface-agnostic.

## Module placement

All edits to existing files; no new files except tests added inside existing test files.

- `src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py` (edit)
- `src/lib/buvis/pybase/zettel/infrastructure/persistence/file_parsers/zettel_file_parser.py` (edit `_get_date_from_file` and its comment)
- `src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py` (edit: remove retry loop, add `_suffixed_id`)
- `src/rust/src/consistency/defaults.rs` (edit `set_default_id`, its doc comment and tests)
- `src/rust/src/parser/enrichment.rs` (edit `date_from_filename`, its doc comment and tests)
- `src/rust/src/scanner.rs` (edit `CACHE_VERSION` 4 -> 5)
- `src/lib/buvis/pybase/zettel/_core.cpython-*.so` is rebuilt locally (not tracked: `.gitignore` has `*.so`; never commit it; see Risks)
- Docs: `src/tools/bim/SKILL.md`, `README.md`, `docs/source/tools/bim.rst`, `CHANGELOG.md`
- Tests: `tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py`, `tests/lib/zettel/infrastructure/test_zettel_file_parser.py`, `tests/lib/zettel/application/test_create_zettel_use_case.py`, `tests/lib/zettel/parity/test_rust_python_parity.py`, `tests/tools/bim/test_create_note_vault.py`

## Interfaces & contracts

### Python `set_default_id(zettel_data: ZettelData) -> None` (signature unchanged)

```python
from datetime import datetime, timezone

date = zettel_data.metadata["date"]
if not isinstance(date, datetime):
    raise ValueError("Invalid date format")
if date.tzinfo is not None:
    date = date.astimezone(timezone.utc)
zettel_data.metadata["id"] = int(date.strftime("%Y%m%d%H%M%S"))
```

- Aware date: UTC digits. Naive date: its own digits, never `astimezone()` (that would read it as system local time).
- Keep the existing `ValueError("Invalid date format")` and `ValueError("Invalid ID format")` behavior.
- Example: `2024-09-13T12:00:00+02:00` -> `20240913100000`; naive `2026-11-17 08:37:39` -> `20261117083739`.

### Python `_get_date_from_file(file_path: Path) -> datetime | None` (signature unchanged)

- When `DATETIME_PATTERN` matches the stem: `digits = m.group()`; if `len(digits) == 14` and `int(digits[12:]) >= 60`, set `digits = digits[:12] + "59"`.
- `fmt = "%Y%m%d%H%M%S" if len(digits) == 14 else "%Y%m%d%H%M"`.
- Return `datetime.strptime(digits, fmt).replace(tzinfo=timezone.utc)`.
- `ValueError` from `strptime` still falls through to the file-system / git fallback, unchanged.
- Comment text: the digits are the note's id, the UTC digits of its date; seconds 60-99 are a collision suffix and read as 59.

### Python `CreateZettelUseCase` (public signatures unchanged)

- `prepare(self, template: ZettelTemplate, answers: dict[str, Any], *, body: str | None = None) -> tuple[Path, Zettel]`
- `execute(self, template: ZettelTemplate, answers: dict[str, Any], *, body: str | None = None) -> Path`
- Remove `MAX_ID_ATTEMPTS`, `import time`, every `time.sleep`, and the `remaining_attempts` parameter/return of `_prepare`.
- New module-level helper, exact name and signature:

```python
def _suffixed_id(base_id: int, seconds: int) -> int:
    """Return base_id with its last two digits replaced by ``seconds`` (60-99)."""
    return int(f"{str(base_id)[:12]}{seconds:02d}")
```

- New private method replacing the old `_prepare` loop (name fixed so tests and planner agree):

```python
def _build(self, template, answers, body) -> tuple[Zettel, list[Path]]:
```

  Builds data ONCE (`template.build_data(answers)`, `_append_body`, `ZettelFactory.create(Zettel(data))`) and returns the zettel plus its ordered candidate paths:
  - slug template (`_retries_on_collision(template)` is False): `[self._path_for(template, zettel)]` only.
  - id template: candidate ids `[base] + [_suffixed_id(base, s) for s in range(60, 100)]` where `base = zettel.id`. When `base` is None or `len(str(base)) != 14`, the only candidate is the base path from `_path_for(template, zettel)` as the zettel stands; never call the `Zettel.id` setter in that case (`int(None)` raises `TypeError`). For a 14-digit base, the base path is `_path_for` as built, and each suffixed path is `_path_for` after `zettel.id = <suffixed id>`; the zettel's `id` must equal the candidate chosen at the end (reset it to the chosen candidate before return).
  - Implementation may compute paths lazily, but the selection order is fixed: base, 60, 61, ..., 99.
- Selection rule (`prepare`): first candidate whose path does not exist. Set `zettel.id = <chosen id>` (id templates only) and `zettel.get_data().file_path = str(path)`. Return `(path, zettel)`.
- Selection rule (`execute`): for each candidate: skip if `path.exists()`; else set `zettel.id`/`file_path`, `path.parent.mkdir(parents=True, exist_ok=True)`, `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)`; `FileExistsError` from that open = collision, take the next candidate. Any other `OSError` propagates (unchanged). The reservation/hooks/save/cleanup block after the loop is unchanged.
- Exhaustion (both methods): `raise FileExistsError(f"Zettel already exists: {base_path}")` where `base_path` is the first candidate path. Message prefix `Zettel already exists: ` is unchanged (SKILL.md and CLI depend on it). No sleep, no rebuild, nothing overwritten.
- The note `date` is never changed by suffixing.

### Rust `set_default_id` (`consistency/defaults.rs`, private, signature unchanged)

```rust
let id_str = dt.with_timezone(&Utc).format("%Y%m%d%H%M%S").to_string();
```

Import `Utc` from chrono. Naive frontmatter dates already arrive as UTC-offset `DateTime<FixedOffset>` (`types.rs`, `NaiveDateTime` branch), so their digits are unchanged. Doc comment: the id is the UTC digits of the date, like the Python fixer.

### Rust `date_from_filename(stem: &str) -> Option<DateTime<FixedOffset>>` (`parser/enrichment.rs`, signature unchanged)

- After the regex match, return `None` when `!matched.is_ascii()` (Rust regex `\d` matches Unicode digits, so byte slicing could panic inside a multi-byte digit; chrono rejects non-ASCII digits anyway, so the result is unchanged). Then, if `matched.len() == 14` and `matched[12..]` parses to `>= 60`, use `format!("{}59", &matched[..12])` as the parse input.
- Parse naive with the same two formats; return `Some(Utc.from_utc_datetime(&naive).fixed_offset())`. Drop `Local` from the imports if no longer used.
- Doc comment: digits are read as UTC; seconds 60-99 read as 59.

### Rust `CACHE_VERSION` (`scanner.rs`)

`const CACHE_VERSION: u8 = 5;`

### New test names (pytest functions are `test_<name>`; Rust tests are `#[test] fn test_<name>`)

| Name | File | Asserts |
|---|---|---|
| `test_utc_id_ignores_local_offset` | `test_set_default_id.py` | `2024-09-13T12:00:00+02:00` -> `20240913100000`; also `-06:00` and `+01:00` inputs of the same instant give the same id |
| `test_naive_date_keeps_its_digits` | `test_set_default_id.py` | naive `2026-11-17 08:37:39` -> `20261117083739` |
| `test_file_name_date_is_utc` | `test_zettel_file_parser.py` | 14- and 12-digit stems give `tzinfo == timezone.utc` with the same wall digits |
| `test_suffix_seconds_map_to_59` | `test_zettel_file_parser.py` | stems `...60`, `...99` -> second 59, UTC |
| `test_same_second_gets_suffix_60` | `test_create_zettel_use_case.py` | base file exists -> path `<base[:12]>60.md`, zettel id equals the suffixed id, both `prepare` and `execute` |
| `test_suffix_runs_to_99` | `test_create_zettel_use_case.py` | base and 60-98 exist -> `...99.md` |
| `test_collision_after_99_raises` | `test_create_zettel_use_case.py` | base and 60-99 exist -> `FileExistsError` matching `Zettel already exists: <base path>`; no file changed; `save` not called |
| `test_lost_reservation_takes_next_suffix` | `test_create_zettel_use_case.py` | `os.open` race on base -> `...60.md`, the racer's content intact |
| `test_create_never_sleeps` | `test_create_zettel_use_case.py` | patch `time.sleep` to raise; a collision path still succeeds |
| `test_rust_python_id_parity_utc` | `test_rust_python_parity.py` | note with `date: 2024-09-13T12:00:00+02:00` -> both paths id `20240913100000` |
| `test_rust_filename_date_utc` | `test_rust_python_parity.py` | stem `20240115143022 ...` and `...60` stem: Python and Rust dates equal as instants, UTC |

Rust unit tests renamed/rewritten: `test_id_keeps_the_dates_own_offset` -> asserts UTC ids (`+02:00 12:00` -> `20240913100000`); `test_default_date_is_local_time_without_subseconds` keeps the local-offset date assertion but its expected id becomes `dt.with_timezone(&Utc).format(...)`; `test_filename_digits_are_local_wall_clock` -> `test_filename_digits_are_utc` plus a 60/99 -> 59 case; new `test_non_ascii_digit_stem_returns_none` (stem `20240115143１` with a fullwidth digit returns `None`, no panic).

## Data flow

1. `bim create` -> `CommandCreateNote` -> `CreateZettelUseCase.prepare/execute`.
2. `_build`: template data -> `ZettelFactory.create` -> consistency fixers -> `set_default_id` writes the UTC base id.
3. Candidate loop: base id, then `_suffixed_id(base, 60..99)`; each candidate updates `zettel.id` and maps to `<vault>/<folder>/<id>.md`.
4. `execute` reserves with `O_EXCL`, runs hooks, saves via the writer; date untouched.
5. Read path: Rust `parse_file`/`load_all` -> `date_from_filename` (UTC, 60-99 -> 59) when no frontmatter date -> `set_default_id` (UTC) when no frontmatter id. Python parser mirrors it; the parity test compares both.
6. Rust cache: version byte 5 discards entries holding old-rule ids/dates on first load.

## Reuse inventory

- `Zettel.id` setter (`domain/entities/zettel/zettel.py:86`): use it to apply the chosen candidate id; it writes `metadata["id"]`.
- `CreateZettelUseCase._path_for` (`create_zettel_use_case.py:55`): reuse unchanged for each candidate (keeps vault confinement check).
- `_retries_on_collision(template)` (`create_zettel_use_case.py:107`): reuse as the slug/id switch.
- `DATETIME_PATTERN` (`zettel_file_parser.py:22`) and `DATETIME_RE` (`enrichment.rs:7`): reuse unchanged.
- `datetime.timezone.utc` (stdlib) and chrono `Utc` / `TimeZone::from_utc_datetime`: the UTC conversion; no new dependency.
- Parity helpers `_rust_dict_to_zettel_data`, `parse_file` (`test_rust_python_parity.py`): reuse for the new parity tests.
- Rust rebuild recipe: project memory "Rust _core rebuild workflow" (maturin build to temp, extract `.so`, `codesign -f -s -`), with `CARGO_HOME`/`CARGO_TARGET_DIR` under the scratchpad.
- Searched for an existing id-allocation/suffix helper: `rg -n "suffix|candidate|next_id|free id|collision" src/lib/buvis/pybase/zettel src/tools/bim` - only `import_helpers.py` integer bump (different rule) and doc naming; nothing reusable.

## Alternatives considered

1. **Smallest diff: keep the loop, swap `time.sleep(1)` + rebuild for a suffix counter.** Keep `_prepare`'s structure and `remaining_attempts`, raise budget to 41. Rejected: still rebuilds the template per attempt (a new `date`/second per build would change the base id mid-loop and break "date not changed" semantics), and keeps a budget variable that has no meaning once candidates are a fixed list.
2. **Chosen: build once, iterate a fixed candidate list.** About the same line count as today; removes the sleep, the budget and the rebuild. The extra size over (1) is a small `_build` method; it buys a deterministic candidate order and one place where prepare and execute share the list.
3. **Allocate by scanning the folder for the highest used suffix.** Rejected: an extra directory scan per create and still needs `O_EXCL` for races; no gain over 40 cheap `exists()` calls.

## Risks & edge cases

- **Rebuild and ad-hoc `codesign` the `_core` `.so` locally** (memory recipe) before running parity tests, or they run Python against the stale extension; on macOS an unsigned `.so` hangs `import _core`. Do not commit it (`*.so` is gitignored); CI and wheel builds compile it from `src/rust`.
- **Non-14-digit ids** (a template that sets its own id): no suffixing, fail fast as today.
- **`exists()` vs `O_EXCL` race**: handled by treating the open's `FileExistsError` as a collision.
- **Python `DATETIME_PATTERN` is `^\d{14}|\d{12}`** (the `\d{12}` branch is unanchored), unlike Rust's anchored group. Pre-existing divergence, out of scope; do not change it here.
- **Legacy notes without `date`** shift by the local offset until PRD 00162 migrates them (accepted in the PRD).
- **PR #275 test** `test_id_cut_from_the_file_creation_time_is_local_wall_clock` may arrive on merge; the PRD says flip it to UTC if present. It is not on this branch at design time.
- Likely next changes: (a) PRD 00162 migration script reads old ids as local time and rewrites them - it needs `_suffixed_id`-compatible collision handling but should not import a private helper; it can reuse the rule, not the symbol. (b) A future `bim` time-zone display setting - unaffected, ids stay UTC. (c) Making `DATETIME_PATTERN` anchored - independent.

## Test strategy outline

- Python unit tests per the table above; replace the tests the PRD names (`test_sets_id_from_dates_own_wall_clock`, `test_14/12_digit_filename_is_local_wall_clock`, `test_raises_file_exists`, all of `TestCollisionBudget`, the parity test `test_default_id_follows_the_dates_own_offset_in_both_paths`); keep `test_slug_collision_fails_without_retry`.
- `tests/tools/bim/test_create_note_vault.py`: change the id assertion to the UTC digits of the saved `date`.
- Existing `test_date_title_from_filename` parity test asserts `202401151030_00` for both paths: still true (UTC digits round-trip), but update its comment from local time to UTC.
- Rust: `cargo test` in `src/rust` with scratch `CARGO_HOME`/`CARGO_TARGET_DIR`.
- Gate: `uv run pytest tests/lib/zettel tests/tools/bim`, `cargo test`, sphinx build; `rg` checks from the PRD acceptance criteria.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 3, question 1
- fixed blocker: the rebuilt `.so` is gitignored; the design now says rebuild and sign locally, never commit.
- non-blocker: the `DATETIME_PATTERN` risk is wrong for the date path. `_get_date_from_file` uses `.match`, which anchors both branches. The divergence exists only in `_get_title_from_filename` (`.sub`). Do not add an anchor to the date parser.
- non-blocker: no rollback statement. A revert is benign. Old parsers run only without a frontmatter `date`, and `bim create` always writes `date` and `id`. A cache version mismatch in either direction causes a rebuild.
- non-blocker: until PRD 00162 runs, ids are not monotonic across the switch, and old local ids can trigger suffixes. Both are accepted by the PRD.
- question: "fail fast as today" for non-14-digit ids is a behavior change, because today they retry with sleep. No shipped template sets its own id. A `None` base is reachable only when a template drops the date.

dispatch 2 (codex): cardinal-sin 0, blocker 2, non-blocker 2, question 0
- note: the first codex run could not read files (sandbox). It was re-run with the doc and code inlined; that run is this dispatch.
- fixed blocker: Rust `matched[12..]` can panic on a stem with Unicode digits. The design now returns `None` for a non-ASCII match, with a test.
- fixed blocker: a `None` base passed to the `Zettel.id` setter raises `TypeError`. The design now never calls the setter for a `None` or non-14-digit base.
- non-blocker: notes named `...60.md` and `...61.md` that have no frontmatter `date` or `id` both get id `...59` on read. Notes made by `bim create` always carry both, so this hits only hand-made files.
- non-blocker: the new collision tests should also assert one template build, an unchanged `date`, and the chosen id in the metadata passed to hooks and save. Planner: fold these assertions into `test_same_second_gets_suffix_60` and `test_lost_reservation_takes_next_suffix`.

dispatch 3 (codex): cardinal-sin 0, blocker 0, non-blocker 3, question 0
- non-blocker: Python and Rust disagree on Unicode suffix digits. Python accepts a stem like `202401151430６０` and Rust returns `None`. This is an edge case for hand-named files only.
- non-blocker: eager candidate generation can reject a free base path when an unused suffix path is a symlink outside the vault. Planner: generate paths lazily, and run `_path_for` only when the loop reaches that candidate.
- non-blocker: a `tzinfo` whose `utcoffset()` returns `None` is still naive. `date.utcoffset() is not None` is the stricter check. The planner may use it in place of `tzinfo is not None`.
