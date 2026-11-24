# Design: 00162 bim one-off script to migrate note ids to UTC

## Architecture fit

The script is a throwaway spike, not product code. It lives in
`docs/dev/project-management/spikes/bim-migrate-ids/`, outside `src/`, so the
`CommandResult`, console, CLI-docs and CHANGELOG invariants of AGENTS.md do not
apply. It imports nothing from `bim` or from the zettel library. Its one
library import is `buvis.pybase.filesystem.atomic_write_bytes` (the AGENTS.md
atomic-persistence invariant). It restates the PRD 00161 UTC id rule (UTC
digits of `date`, `%Y%m%d%H%M%S`; collisions take seconds `60` to `99`)
instead of importing it.

pytest runs with `--import-mode=importlib` and `testpaths = ["tests"]`
(`pyproject.toml:107-110`). An explicit path argument overrides `testpaths`,
so the gate `uv run pytest docs/dev/project-management/spikes/bim-migrate-ids`
collects the spike test file. `tests/conftest.py` does not apply there, so no
tool marker is added. `pythonpath` holds `src/lib`, so `buvis.pybase` imports
in tests; the subprocess `--help` test runs under `sys.executable` of the uv
venv, where `buvis-gems` is installed editable.

## Module placement

New files only:

- `docs/dev/project-management/spikes/bim-migrate-ids/migrate_ids.py` - the
  script (plan, apply, undo, `main`). Target size under 700 lines (800 max).
- `docs/dev/project-management/spikes/bim-migrate-ids/test_migrate_ids.py` -
  one test per PRD rule, the 23 names of the PRD, plus helper fixtures in the
  same file. Target size under 800 lines.

No edit to any existing file. No `CHANGELOG.md` entry, no `SKILL.md` or docs
change (PRD Exit Criteria).

## Interfaces & contracts

All names live in `migrate_ids.py`. Module header:

```python
from __future__ import annotations
import argparse, hashlib, json, os, re, sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from buvis.pybase.filesystem import atomic_write_bytes
```

`atomic_write_bytes` MUST be imported into the module namespace with exactly
this `from` import and every file write MUST call it through the module global
name `atomic_write_bytes`. Tests replace `migrate_ids.atomic_write_bytes` with
`monkeypatch.setattr` to inject a write error.

### Constants

```python
DEFAULT_ZONE = "Europe/Prague"
SUFFIX_SECONDS = range(60, 100)      # 60..99 inclusive
MAP_VERSION = 1
TEMP_SUFFIX = ".migrating"           # temp file name: f"{path.name}.{run_id}{TEMP_SUFFIX}"
```

Skip reasons are these exact strings (used in the dry-run table and in tests):

```python
REASON_AMBIGUOUS = "ambiguous local time (DST fold)"
REASON_NONEXISTENT = "nonexistent local time (DST gap)"
REASON_DATE_ONLY = "date has no time"
REASON_UNPARSEABLE = "date cannot be parsed"
REASON_BAD_ID_TIME = "old id is not a valid time"
REASON_NO_SUFFIX = "no free collision suffix 60-99"
REASON_NOT_UTF8 = "frontmatter is not UTF-8"
REASON_SYMLINK = "file is a symlink"
REASON_STEM_SHARED = "old stem shared with another file"
REASON_TYPE_UNKNOWN = "type is a block scalar or empty"
```

### Byte regexes (frontmatter is edited as bytes, never as YAML)

```python
_EOL = rb"[ \t]*(?:[ \t]#[^\r\n]*)?\r?$"   # trailing blanks, optional YAML comment, CR
FRONTMATTER = re.compile(rb"\A---\r?\n(.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.S)
ID_LINE = re.compile(rb"^id:[ \t]*([\"']?)(\d{14}|\d{12})\1" + _EOL, re.M)
TYPE_DOCUMENT = re.compile(rb"^type:[ \t]*([\"']?)document\1" + _EOL, re.M)
DATE_LINE = re.compile(rb"^date:[ \t]*([\"']?)(.*?)\1" + _EOL, re.M)
_CONTAINER = rb"[ \t]*(?:>[ \t]?)*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)?"   # blockquote and list-item prefixes
_CLOSER = rb"[ \t]*(?:>[ \t]?)*"
FENCE = re.compile(
    rb"^" + _CONTAINER + rb"(`{3,})[^\n]*\n.*?(?:^" + _CLOSER + rb"\1`*[ \t]*\r?$|\Z)"
    rb"|^" + _CONTAINER + rb"(~{3,})[^\n]*\n.*?(?:^" + _CLOSER + rb"\2~*[ \t]*\r?$|\Z)",
    re.S | re.M,
)
TYPE_BLOCK = re.compile(rb"^type:[ \t]*(?:[|>][^\r\n]*)?\r?$", re.M)   # type with no value on its line
INLINE_CODE = re.compile(rb"(?<!`)(`+)(?!`)(?:(?!\n[ \t]*\r?\n).)*?(?<!`)\1(?!`)", re.S)
```

`ID_LINE`, `TYPE_DOCUMENT` and `DATE_LINE` are searched only inside the
frontmatter span (`pattern.search(data, fm.start(), fm.end())`). A trailing
` # comment` is allowed and kept; `DATE_LINE` group 2 never includes it.

```python
def protected_spans(data: bytes) -> list[tuple[int, int]]:
    """Fence spans first (a closer may be longer than the opener; a fence may
    sit in a blockquote; an unclosed fence runs to end of file), then
    INLINE_CODE spans searched only in the gaps between fences, so an inline
    backtick never pairs across a fence."""
```

Protected spans are never rewritten and never scanned. Everything else of a
file, frontmatter included, is rewritten and scanned.

### Reference pattern

```python
def stem_pattern(stems: Iterable[str]) -> re.Pattern[bytes]:
    """[[ + optional folder path ending in / + one stem + optional .md, then | or # or ]]."""
```

Body: alternation of `re.escape(stem.encode())` sorted by length descending,
inside
`rb"(\[\[(?:[^\[\]|#\n]*/)?)(" + alts + rb")(?=(?:\.md)?(?:\\?\||#|\]\]))"`.
Group 1 is the `[[` plus folder prefix, group 2 the stem. The stem must start
right after `[[` or `/` and end right before `.md`, `|`, `\|` (table-escaped
alias), `#` or `]]`, so a
digit string inside a longer digit string, plain text, and Markdown links
`[..](<id>.svg)` / `file://` links never match. `![[`, `key:: [[` and
frontmatter `"[[...]]"` values match because the match starts at `[[`.
Callers never build a pattern from an empty stem set: with no renamed note,
the rewrite and the leftover scan are skipped.

```python
def rewrite_references(data: bytes, pattern: re.Pattern[bytes], stem_map: Mapping[str, str]) -> tuple[bytes, int]:
    """One pass over the unprotected spans; returns new bytes and the count of rewritten references."""
```

Replacement: `group(1) + stem_map[group(2)].encode()`. One `pattern.sub` per
unprotected span, so a rewritten stem is never matched again in the same
pass.

### Time zone resolution

```python
def resolve_date(value: str, zone: ZoneInfo) -> tuple[datetime, bool] | str:
    """Return (aware date, date_changed) or a REASON_* string."""
```

- strip one pair of surrounding quotes is already done by `DATE_LINE` group 1;
- no time part (`not re.search(r"\d[T ]\d", value)`): `REASON_DATE_ONLY`
  when `date.fromisoformat(value)` succeeds (this catches `2024-03-01`,
  `20240301` and `2024-W09-1`, which `datetime.fromisoformat` reads as
  midnight), else `REASON_UNPARSEABLE`;
- `datetime.fromisoformat(value)` raising `ValueError` -> `REASON_UNPARSEABLE`;
- aware result -> `(dt, False)` (offset kept);
- naive result -> `localize(dt, zone)`; aware -> `(aware, True)`;
- `OverflowError` from the UTC conversion (year 1 or 9999 edges) ->
  `REASON_UNPARSEABLE`.

```python
def localize(naive: datetime, zone: ZoneInfo) -> datetime | str:
```

`a = naive.replace(tzinfo=zone, fold=0)`, `b = naive.replace(tzinfo=zone, fold=1)`.
When `a.utcoffset() == b.utcoffset()` return `a`. Otherwise, when
`a.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive` return
`REASON_NONEXISTENT`, else `REASON_AMBIGUOUS`.

A note without a `date` line uses its old id: 12 digits get `"00"` seconds,
`datetime.strptime(digits, "%Y%m%d%H%M%S")` raising `ValueError` ->
`REASON_BAD_ID_TIME`, else `localize(...)`; `date_changed = True`.

New date line bytes:

- naive `date` present: the original line with the offset text
  `aware.replace(microsecond=0).isoformat()[19:]` (`+HH:MM`, or
  `+HH:MM:SS` for an offset with seconds) inserted right after the value
  (end of `DATE_LINE` group 2), inside any quotes and before any comment: `date: 2024-03-01 10:00:00` ->
  `date: 2024-03-01 10:00:00+01:00`. Every other byte of the line stays.
- no `date` line: a new line `b"date: " + aware.isoformat().encode()` with the
  same line ending as the `id` line, inserted directly after the `id` line.
- aware `date`: unchanged.

### Data model

```python
@dataclass(frozen=True)
class NoteChange:
    path: Path            # absolute old path
    new_path: Path        # absolute; equals path when the stem does not start with the old id or the id is unchanged
    old_id: str
    new_id: str           # equals old_id for an "already on UTC" note
    old_date_line: str | None   # decoded line without line ending; None when the note had no date line
    new_date_line: str
    date_changed: bool

@dataclass(frozen=True)
class Skip:
    path: Path
    reason: str           # one REASON_* constant

@dataclass(frozen=True)
class Plan:
    vault: Path                       # resolved
    naive_timezone: str
    changes: tuple[NoteChange, ...]   # notes whose id, file name or date line change, sorted by (old_id, path)
    skips: tuple[Skip, ...]
    already_utc: tuple[Path, ...]     # new_id == old_id (date line may still change)
    local_digit_mismatch: tuple[Path, ...]  # old id (12 digits padded "00") != wall-clock digits of the resolved date
    kept_attachments: tuple[Path, ...]      # non-.md files under notes/ whose stem starts with a migrating old id
    reference_count: int              # references the apply will rewrite
    hashes: Mapping[Path, str]        # sha256 hex of every .md under notes/ as read by the plan

class MigrationError(Exception):
    """Any premise or apply failure; the message names the file."""
    def __init__(self, message: str, map_file: Path | None = None) -> None:
        super().__init__(message)
        self.map_file = map_file   # set for every error raised after apply step 4

@dataclass(frozen=True)
class ApplyResult:
    map_file: Path
    outside_references: tuple[Path, ...]   # .md files outside notes/ that link to an old stem; not rewritten

@dataclass(frozen=True)
class UndoReport:
    restored: tuple[Path, ...]
    unchanged: tuple[Path, ...]
    skipped: tuple[Path, ...]   # changed since apply; left untouched
```

### Public functions

```python
def plan_migration(vault: Path, naive_timezone: str = DEFAULT_ZONE) -> Plan:
def apply_migration(plan: Plan, map_dir: Path, *, now: datetime | None = None) -> ApplyResult:
def undo_migration(vault: Path, map_file: Path) -> UndoReport:
def default_map_dir() -> Path:
def main(argv: list[str] | None = None) -> int:
```

`plan_migration` raises `MigrationError` when `vault / "notes"` is not a
directory or is a symlink. It never writes.

Selection rules (inside `plan_migration`):

- scan `sorted((vault / "notes").rglob("*.md"))`; a symlink leaf is checked
  with `is_symlink()` before any read and becomes `Skip(REASON_SYMLINK)`
  (never read, rewritten or scanned); a non-regular entry (a directory named
  `*.md`) is ignored; every regular file is read with `path.read_bytes()`;
- a file with an `ID_LINE` and a `TYPE_BLOCK` match is
  `Skip(REASON_TYPE_UNKNOWN)`: its type cannot be read from one line, so it
  might be a document zettel;
- a file is a note when its frontmatter has an `ID_LINE` match and no
  `TYPE_DOCUMENT` match; a `type: document` file and a file without an `id`
  line get no mapping entry but are rewritten;
- `default_map_dir()` = `Path(os.environ["XDG_STATE_HOME"]) / "bim" / "migrate-ids"`
  when the variable is set and not empty, else
  `Path.home() / ".local" / "state" / "bim" / "migrate-ids"`.

Mapping rules:

- base new id = `aware.astimezone(UTC).strftime("%Y%m%d%H%M%S")`;
- a note is "renaming" when `stem.startswith(old_id)` and
  `not stem[len(old_id):len(old_id) + 1].isdigit()`; its
  `new_path = path.with_name(new_id + stem[len(old_id):] + path.suffix)`.
  Otherwise `new_path == path`;
- Obsidian resolves `[[stem]]` by bare stem across the vault, so stems are
  compared vault-wide, never per folder, and casefolded (macOS file systems
  are case-insensitive). `vault_md_stems` = a `Counter` of casefolded stems
  of every `.md` file under `vault`, excluding the `.obsidian` and `.trash`
  folders;
- a renaming note whose old stem occurs more than once in `vault_md_stems` is
  `Skip(REASON_STEM_SHARED)`: its links are ambiguous and the mapping is
  keyed by bare stem. An `<id>.svg` attachment with the same stem does not
  count; it keeps its name and its links (`![[<id>.svg]]`) end in an
  extension that the reference pattern refuses;
- `taken_ids` starts with the `ID_LINE` id of every `.md` file under `notes/`
  whose id does not change: skipped notes, `type: document` zettels, notes
  with `new_id == old_id`. `occupied_stems` = the casefolded stems of every
  entry under `vault` (files, directories and symlinks, any extension,
  `.obsidian` and `.trash` excluded) that stays at its path, i.e. every entry
  except the renaming notes themselves; an `<id>.svg` beside a renaming
  `<id>.md` therefore keeps `<id>` occupied. It also holds the casefolded
  last path component (before `|`, `\|`, `#` and an optional `.md`) of every
  wikilink target found in the unprotected spans of every `.md` under
  `notes/`, minus the old stems of renaming notes; so a new stem never equals
  a stem that some file already links to, and the apply step 3 check cannot
  fail on a pre-existing `[[<new stem>]]`;
- notes that change id are processed in `(old_id, path)` order; a candidate id
  is the base, then `base[:12] + f"{s:02d}"` for `s` in `SUFFIX_SECONDS`; a
  candidate is free when it is not in `taken_ids` and, for a renaming note,
  its casefolded new stem is not in `occupied_stems`. The chosen id joins
  `taken_ids` and the chosen new stem joins `occupied_stems`. None free ->
  `Skip(REASON_NO_SUFFIX)`;
- a `REASON_NO_SUFFIX` skip keeps its old id and old stem, which earlier
  notes may already hold. When a round produced such a skip, move the
  skipped note into the kept set (its id into `taken_ids`, its stem into
  `occupied_stems`) and run the loop again from the start; stop when a round
  adds no new skip. Rounds are bounded by the number of notes;
- `stem_map` = `{old stem: new stem}` for renaming notes only; old stems are
  unique by the shared-stem rule above;
- two notes with the same old id but different stems are planned per file
  (the map file is per file), so each may get its own new id; the dry-run
  table shows both rows.

`apply_migration` steps, in this order; any `OSError` is re-raised as
`MigrationError` naming the file, and the map file is never deleted:

1. Premise: `main` compares `Path(args.vault).resolve()` with `plan.vault`
   before it calls `apply_migration` (the function itself has no second vault
   value to compare). `apply_migration` checks that `map_dir.resolve()` is not
   `plan.vault` and not inside it (`is_relative_to`) -> else `MigrationError`
   before any write.
2. Compute in memory, for every `.md` under `notes/` (not symlinks): `before`
   bytes, `after` bytes (note edits, then `rewrite_references` with
   `stem_map`). The set of `.md` files and the sha256 of every `before` must
   equal `plan.hashes`; any difference (a file edited, added or removed since
   the plan) -> `MigrationError` before any write. Keep only files where
   `after != before` or the path changes.
   Run the leftover scan (step 7 pattern) on every `after` buffer now; any
   hit -> `MigrationError` before any write. Also scan, read-only, every other
   `.md` under `vault` (`.obsidian` and `.trash` excluded) with
   `stem_pattern` over the old stems; hits are returned as
   `outside_references` and printed as warnings, never rewritten (the PRD
   forbids changing templates).
3. Reversibility check: for every kept file, `reverse(after) == before`, where
   `reverse` applies the inverse note edits and `rewrite_references` with the
   inverse `stem_map`. Any mismatch -> `MigrationError` before any write (this
   catches a file that already links to a new stem).
4. Write the map file `map_dir / f"{run_id}.json"`, with
   `run_id = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")`;
   an existing file of that name -> `MigrationError`. `map_dir` is created with
   `mkdir(parents=True, exist_ok=True)`. Written with `atomic_write_bytes`.
5. Phase A: `os.rename(path, temp)` for every renamed file, `temp` =
   `path.with_name(f"{path.name}.{run_id}{TEMP_SUFFIX}")`, `run_id` = the map
   file stem. A `temp` that exists -> `MigrationError`.
6. Phase B: for every kept file, `atomic_write_bytes(new_path, after)`, then
   `temp.unlink()` for a renamed file. For a renamed file only: a `new_path`
   that exists and is not a path vacated in phase A -> `MigrationError`.
   Non-renamed files are written in place.
7. Leftover scan (the PRD's post-write scan, repeated from disk): every `.md`
   under `notes/` (not symlinks), unprotected spans only, with
   `leftover_pattern(stems)` over the old stems that are not also new stems.
   It is deliberately looser than `stem_pattern`, to catch link targets the
   rewrite does not know, but it looks only at the link target (before `|`,
   `\|` or `#`) and refuses an attachment extension:
   ```python
   def leftover_pattern(stems: Iterable[str]) -> re.Pattern[bytes]:
       # alts as in stem_pattern
       return re.compile(
           rb"\[\[[^\]|#\n\\]*?(?<![0-9A-Za-z_-])(" + alts + rb")"
           rb"(?![0-9A-Za-z_-])(?!\.(?!md(?![0-9A-Za-z]))[0-9A-Za-z])[^\]|#\n\\]*(?:\\?\||#|\]\])"
       )
   ```
   So `[[<old> ]]` and `[[notes/<old>.md]]` hit; `![[<old>.svg]]`,
   `![[<old>.png|200]]`, `[[x|<old>]]` (alias), `[[<old>_a]]` and
   `[[<old>-meeting]]` do not. Any hit -> `MigrationError` listing the files.
8. Return `ApplyResult(map_file, outside_references)`.

Map file JSON (UTF-8, `indent=2`, `sort_keys=True`):

```json
{
  "version": 1,
  "vault": "/abs/vault",
  "run_id": "20261124T213000Z",
  "naive_timezone": "Europe/Prague",
  "files": [
    {
      "old_path": "notes/20240301100000.md",
      "new_path": "notes/20240301090000.md",
      "temp_path": "notes/20240301100000.md.20261124T213000Z.migrating",
      "sha256_before": "<hex>",
      "sha256_after": "<hex>",
      "old_id": "20240301100000",
      "new_id": "20240301090000",
      "old_date_line": "date: 2024-03-01 10:00:00",
      "new_date_line": "date: 2024-03-01 10:00:00+01:00"
    }
  ]
}
```

Paths are POSIX, relative to `vault`. `temp_path` is `null` when the file is
not renamed. `old_id`, `new_id`, `old_date_line`, `new_date_line` are `null`
for a file that only gets references rewritten (a file that is not a note
still gets a map record, because undo restores its bytes; it gets no id or
stem mapping); `old_date_line` is `null` when the note had no date line.

`undo_migration` steps:

1. Premise, before any write, else `MigrationError`: the JSON parses and has
   every key of the schema with the right type (`temp_path`, `old_id`,
   `new_id`, `old_date_line`, `new_date_line` may be `null`); `version == 1`;
   `vault.resolve()` equals the map's `vault`; `run_id` matches
   `\d{8}T\d{6}Z`; each hash matches `[0-9a-f]{64}`; every non-null path is
   relative, has no `..` part, and resolves inside `vault / "notes"`; no two
   entries share an `old_path` or a `new_path`; `vault / "notes"` is not a
   symlink.
2. Classify each entry, first rule that holds. `undo_temp` =
   `new_path.with_name(f"{new_path.name}.undo-{run_id}{TEMP_SUFFIX}")`
   (named after `new_path`, so its name is fixed for every rerun);
   `owner_before` = the `sha256_before` of the entry whose `old_path` equals
   this entry's `new_path`, if any (for an in-place entry that is itself):
   1. `old_path` holds `sha256_before` -> unchanged (never changed, or
      restored by a stopped earlier undo). Tool temps of this entry that are
      now redundant (`temp_path` with `sha256_before`, `undo_temp` with
      `sha256_after`) are removed.
   2. `new_path` holds `sha256_after` -> restore from `new_path`.
   3. `undo_temp` holds `sha256_after` -> restore from `undo_temp` (a stopped
      earlier undo).
   4. `new_path` exists and its hash is neither `sha256_after` nor
      `owner_before` -> skipped (edited since apply; `temp_path` is left).
   5. `temp_path` holds `sha256_before` -> restore from `temp_path` (bytes
      already original, no transform). This covers a stop inside apply
      phase A, where `new_path` may still hold the untouched file of another
      entry.
   6. else skipped.
   A restore from `new_path` or `undo_temp` also removes a `temp_path` that
   holds `sha256_before` once the restored file is written.
3. Fixpoint, before any write. Repeat until a round adds no skip:
   - the inverse stem map holds only renamed entries that are restored;
     skipped renamed notes keep their new stem;
   - for each restore from `new_path` or `undo_temp`, `before = reverse(after)`
     with that inverse map; `sha256(before) != sha256_before` -> skipped (its
     references are not rewritten);
   - a skipped file that links (`stem_pattern` over the new stems,
     unprotected spans) to the new stem of a renamed entry forces that entry
     into skipped, so no kept link loses its target. Unchanged files are not
     checked: they hold their before bytes, so their links name old stems
     (checking them stranded a chain note in its temp file after a stop in
     apply phase A);
   - a restore whose `old_path` exists and is not a source this undo stages
     away -> skipped (blocked chain).
   Each round only adds skips, so the loop ends.
4. Execute with the same phase A / phase B as apply. Phase A stages only
   sources at `new_path` (to `undo_temp`); sources already at `undo_temp`
   or `temp_path` are not staged again. Phase B writes `old_path`, then
   removes the source temp.
5. Return `UndoReport`; the CLI lists skipped paths and the new stems that
   stay because their undo was skipped.

CLI (`main`):

```
migrate_ids.py --vault PATH [--naive-timezone ZONE] [--apply | --undo MAPFILE]
```

`--apply` and `--undo` are a mutually exclusive group. No flag = dry run.
Output with `print` to stdout; errors to stderr. Exit codes: `0` success,
`1` `MigrationError` or leftover, `2` argparse usage error. A `ZoneInfo`
lookup failure is a `MigrationError`. `if __name__ == "__main__": sys.exit(main())`.

Dry-run output: one table row per change (`old path -> new path`,
`old id -> new id`, `date changed`), then the counts: notes to migrate (id
changes), notes already on UTC, skipped notes per reason, notes whose old id
differs from the local digits of `date`, references to rewrite, id-named
attachments that keep their names, then the line "Back up the vault and close
Obsidian before --apply." `--apply` prints the same line first. After
`--apply`: the map file path, the `outside_references` warnings, and the reminder
"delete ~/.cache/buvis/zettel_cache.bin". A `MigrationError` raised after the
map file exists prints the map file path to stderr with the hint
`--undo <path>`. After `--undo`: the three `UndoReport` counts, the skipped
paths and the cache reminder.

## Data flow

1. `main` -> `plan_migration(vault, zone)`: read bytes -> frontmatter span ->
   `ID_LINE` / `TYPE_DOCUMENT` / `DATE_LINE` -> `resolve_date` or id fallback
   -> base id -> collision loop -> `NoteChange` / `Skip` -> `Plan` with counts
   (references counted with `rewrite_references` in memory).
2. Dry run prints the plan and stops.
3. `--apply` -> `apply_migration(plan, default_map_dir())`: in-memory after
   bytes -> reversibility check -> map file -> phase A temp renames -> phase B
   atomic writes -> leftover scan.
4. `--undo MAPFILE` -> `undo_migration(vault, mapfile)`: read map -> classify
   by hashes -> reverse bytes -> verify hash -> phase A / phase B.

## Reuse inventory

- `src/lib/buvis/pybase/filesystem/atomic_write.py:71` `atomic_write_bytes(path, data)`
  - every file write, map file included. It keeps permission bits of an
  existing target and replaces a symlink with a plain file, hence symlinks are
  excluded.
- `tests/dev/test_scaffold.py:9-14` - the `importlib.util.spec_from_file_location`
  load pattern for a non-package script; the test file copies it with
  `Path(__file__).with_name("migrate_ids.py")` and registers
  `sys.modules["migrate_ids"]` before `exec_module` (dataclasses need it).
- `src/tools/bim/shared/vault_links.py:18-21` `PROTECTED` - the inline-code
  and fence pattern; restated in bytes (wikilink and URL alternatives dropped,
  because wikilinks are the target here) since the PRD forbids importing bim.
- `src/lib/buvis/pybase/zettel/infrastructure/persistence/file_parsers/zettel_file_parser.py:22`
  `DATETIME_PATTERN` - confirms ids are 12 or 14 digits; not imported.
- Wikilink rewrite / rename helpers: nothing found, greps tried:
  `rg -i "wikilink|rewrite_links|rename.*link|backlink" src` (hits only
  `vault_links.py`, which adds links, never renames), control hit
  `atomic_write` proved the search works.

## Alternatives considered

1. **Store each file's original bytes in the map file (base64).** Undo copies
   them back; no reverse transform. Good: undo is trivially lossless. Bad: the
   map grows to the size of every changed file and departs from the PRD's map
   contents. Rejected; the reversibility check of apply step 3 gives the same
   guarantee with hashes only.
2. **Edit notes through the zettel library (parse + format).** Rejected:
   re-serializes YAML, changes bytes the PRD says must stay, and imports code
   the PRD forbids.
3. **Smallest diff: topological rename order plus a temp only for cycles
   (chosen idea's sibling).** Fewer renames, but stopped-apply states multiply
   (a cycle member at a temp, others in place) and undo needs the same graph
   logic. The chosen design moves every renamed file to a temp first, then
   writes; one rule covers chains, swaps and undo, at the cost of one extra
   rename per renamed file.

Chosen: byte edits + two-phase temp rename + hash-verified reverse transform.

## Risks & edge cases

- Rollback: `--undo MAPFILE` is the in-tool rollback; the independent one is
  the vault backup the owner takes before `--apply` (PRD hand-off; the dry run
  prints the reminder). The script does not copy the vault itself: the
  backup is the owner's step, by PRD scope.
- Memory: apply holds `before` and `after` of every `.md` under `notes/`
  (about twice the Markdown size of one personal vault, tens of MB) and one
  regex over the renamed stems. Accepted without limits: the script runs once,
  by its owner, on one known vault.
- Two files with the same old id: each is planned on its own path; the
  occupied-stem check stops two from claiming one new stem.
- Chains in the leftover scan: an old stem that is also a new stem is not
  scanned (PRD rule), so a missed link to it cannot be detected by stem
  alone. The reference pattern rewrites every listed form in one pass; the
  scan catches forms it does not know only for the other stems.
- `leftover_pattern` can hit a target that holds an old stem as a token
  inside a longer title (`[[meeting (<id>)]]`). It fails before any write
  (apply step 2), so the cost is a rerun after editing that link.
- A file that already links to a new stem: caught by the reversibility check
  before any write; the run aborts and names the file.
- A crash between phase A and phase B leaves `*.migrating` files; undo
  restores them from `temp_path`.
- Obsidian open during the run: out of scope in code; undo's hash check skips
  files changed afterwards.
- `fromisoformat` accepts `T` or space, `Z`, `+HHMM` and fractions on Python
  3.11+; fractions are kept in the line and ignored for the id.
- References outside `notes/` (templates, `.obsidian`) are not rewritten; the
  PRD forbids changing templates.
- Likely next changes: rerun on the bim archive (a second `--vault`-like root;
  `plan_migration` takes the notes root from `vault`, so a `notes_dir`
  parameter would be the change); a `--map-dir` flag (the function already
  takes `map_dir`); 00165 Prague rule in bim itself (independent; the script
  restates the rule).

## Test strategy outline

All tests in `test_migrate_ids.py`, each building a fixture vault under
`tmp_path / "vault" / "notes"` and a map dir `tmp_path / "state"`; none writes
to the real home (`monkeypatch.setenv("XDG_STATE_HOME", ...)` for the CLI).

- Plan: `prague_dst_summer_offset` (naive July -> `+02:00`, id = local - 2h),
  `prague_dst_winter_offset` (January -> `+01:00`), `aware_date_keeps_offset`,
  `ambiguous_dst_time_is_skipped` (2024-10-27 02:30), `nonexistent_dst_time_is_skipped`
  (2024-03-31 02:30), `date_only_is_skipped` (`2024-03-01` and `20240301`), `note_without_date_uses_old_id`
  (12-digit id, date line inserted), `document_zettel_is_not_migrated` (also
  `type: document # scanned`),
  `slug_named_note_keeps_file_name` (`contact/<slug>.md` gets a new id line
  only), `file_without_id_is_not_a_note` (daily note gets references
  rewritten, no id or stem mapping; its map record has null note fields), `same_new_id_gets_suffix_60` (also: a note whose
  base id equals a `type: document` zettel's id takes `60`; two notes with
  one stem in different folders are both `REASON_STEM_SHARED`).
- Apply: `apply_rewrites_all_reference_forms` (`[[x]]`, `![[x]]`,
  `[[notes/x|a]]`, `[[notes/f/x#h]]`, `key:: [[x]]`, frontmatter
  `"[[x]]"`), `longer_digit_string_is_not_a_reference`,
  `attachment_links_untouched` (`![..](<id>.svg)`, `file://`,
  `![[<id>.svg]]`, `![[<id>.png|200]]`; the `.svg` keeps its name and the
  apply succeeds), `code_fences_untouched` (also a longer closing fence, a
  fence in a blockquote, a fence on a `- ` list item, CRLF), `leftover_reference_fails_apply` (fixture
  link `[[<old stem> ]]` with a trailing space: the rewrite skips it, the
  in-memory scan of apply step 2 finds it; `apply_migration` raises
  `MigrationError`, no map file is written and every file hash is
  unchanged), `undo_restores_bytes` (hash of every file, one CRLF note; plus
  a case where one renamed note is edited after the apply: undo skips it,
  leaves links to it on its new stem, restores the rest, and a referrer that
  links to both the edited note and another renamed note keeps both links
  resolvable),
  `stopped_apply_then_undo_restores_bytes` (monkeypatched
  `atomic_write_bytes` raises on the third call; the error carries
  `map_file`; a second case stops phase A of a chain `A -> B -> C` after the
  first `os.rename` (monkeypatched `migrate_ids.os.rename`), and a third case
  stops an undo after its first write, then reruns undo; every case ends
  with every byte and name restored and no `*.migrating` file left),
  `chain_and_swap_rename_safely`, `link_not_rewritten_twice`,
  `frontmatter_other_bytes_unchanged`, `dry_run_writes_nothing` (snapshot of
  every path and hash before and after `main(["--vault", ...])`).
- CLI: `script_help_lists_apply_and_undo` runs
  `[sys.executable, "docs/dev/project-management/spikes/bim-migrate-ids/migrate_ids.py", "--help"]`
  with `cwd` = repo root and checks `--apply` and `--undo` in stdout.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 6, question 5

- Fixed blocker: the leftover scan hit `![[<id>.svg]]` embeds and alias text and ran only after the writes. `leftover_pattern` now reads only the link target, refuses attachment extensions and treats `_`/`-` as part of the token. It also runs in memory before any write (apply step 2).
- Fixed blocker: collisions were checked per folder and per id of notes only. Stems are now compared vault-wide (`all_stems`, `occupied_stems`). `taken_ids` holds every id that does not change, document zettels included. A shared old stem is skipped (`REASON_STEM_SHARED`).
- Question (clarified in the doc): chosen ids join `taken_ids`; a `REASON_NO_SUFFIX` skip re-runs the loop until no new skip.
- Question (clarified in the doc): apply step 1's vault premise moved to `main`; the phase B existence check applies to renamed files only.
- Question: undo with a skipped renamed note leaves links to its old stem dead. Intended reading of the PRD: the skipped file itself is not touched. Report those stems in the undo output.
- Question: the leftover scan covers `notes/` only, while the PRD says "every `.md` file". Deliberate: templates must not change and the rewrite scope is `notes/`.
- Non-blocker: a file that already links to a new stem aborts the run. Option: add existing link targets to `occupied_stems`.
- Non-blocker: a stopped undo can leave `undo-` temp files, and an apply temp beside a restored `new_path` is not removed. Check all destinations before phase A; remove a leftover `temp_path` on restore.
- Non-blocker: rewritten files lose mtime and mode (a new path gets 0644). Option: record and restore `st_mode`/`st_mtime_ns` with `os.chmod`/`os.utime`.
- Non-blocker: `PROTECTED` closes a fence only on the same-length marker; a longer closing fence protects to end of file.
- Non-blocker: `fromisoformat` accepts `20240301` and `2024-W09-1` as midnight; the date-only check misses them. Use "no time separator" as the test.
- Non-blocker: a failed apply does not print the map file path; the undo output lacks the cache reminder. (Adopted after dispatch 2: `MigrationError.map_file`, cache reminder after undo.)

dispatch 2 (codex): cardinal-sin 2, blocker 11, non-blocker 1, question 1

- Fixed cardinal sin (no independent backup): Risks now names the owner's pre-apply vault backup as the independent rollback, beside `--undo`. The dry run prints the reminder. Copying the vault in code is out of PRD scope.
- Fixed cardinal sin (unbounded memory): Risks accepts the bound explicitly. The script runs once, by its owner, on one known vault, and needs about 2x the Markdown size.
- Fixed blocker (undo strands a chain): undo step 3 is a fixpoint before any write. A restore whose `old_path` stays occupied is skipped.
- Fixed blocker (apply temp overrides a changed file): undo classifies `new_path` first. A changed `new_path` is skipped and its temp is ignored. A redundant temp is removed after a verified restore.
- Fixed blocker (partial undo reverses links to skipped files): the inverse stem map holds only restored entries. A referrer whose hash then fails is skipped too, so links stay valid.
- Fixed blocker (edits after planning): `Plan.hashes` binds the plan to its input. Apply step 2 refuses any drift before a write.
- Fixed blocker (paths escape the vault): undo step 1 confines every map path to `vault/notes`. A symlinked notes root is refused, and symlink leaves are skipped before they are read.
- Fixed blocker (occupancy lost an attachment's stem; per-notes inventory): `occupied_stems` holds every file that stays. Stems are vault-wide (`.obsidian`/`.trash` excluded) and casefolded.
- Partly fixed blocker (leftover scan): the scan runs in memory before any write. The chain case (an old stem that is also a new stem) follows the PRD rule and is recorded in Risks. The token false positive fails before any write and is recorded in Risks. The `notes/` scope is deliberate, see the dispatch 1 question.
- Fixed blocker (code protection): `FENCE` accepts longer closers and blockquote fences. `protected_spans` finds fences before inline code.
- Fixed blocker (YAML comments): `_EOL` allows a trailing ` # comment` on `id`, `type` and `date`.
- Fixed blocker (date parsing): date-only means no time part. The offset is written with seconds when it has them. `OverflowError` is a skip.
- Fixed blocker (tests contradicted the contract): `leftover_reference_fails_apply` expects no map and no change. A non-note file gets a map record with null note fields.
- Non-blocker: the global inverse in the reversibility check rejects a file that already links to a new stem (same as the dispatch 1 non-blocker).
- Question (answered in Mapping rules): duplicate old ids with distinct stems are planned per file.

dispatch 3 (codex): cardinal-sin 2, blocker 11, non-blocker 1, question 1

Adjudicated by the author after the 3-dispatch ceiling. No reviewer verified these changes; the work-completion review covers them.

- Rejected cardinal sin (independent restore untested): the PRD scope puts the vault backup on the owner ("the owner runs the dry run and the apply by hand after a backup"). The tested rollback is `--undo` (`undo_restores_bytes` and `stopped_apply_then_undo_restores_bytes`). Adopted the cheap part: `--apply` also prints the backup line first.
- Rejected cardinal sin (no enforced resource limit): Risks accepts the bound explicitly and gives the reason (one run, one owner, one known vault). The cardinal sin is an unbounded consumption that nobody accepted, and this one is accepted.
- Fixed blocker (a stop in phase A strands a chain): undo classification is reordered. `old_path` with the before hash comes first. A `new_path` that holds another entry's untouched file (`owner_before`) no longer blocks a restore from `temp_path`. An in-place entry is unchanged. Test case added.
- Fixed blocker (a stopped undo loses its temps): `undo_temp` is named after `new_path` and is fixed across reruns. Temps are never staged again. A restored `old_path` reads as unchanged and its redundant temps are removed. Test case added.
- Fixed blocker (partial undo breaks links from skipped referrers): the fixpoint also forces a renamed entry into skipped when a kept file links to its new stem. Test case added.
- Rejected blocker (overwrite at a vacated path by a concurrent writer): PRD Risks says "Obsidian rewrites files while the script runs: Mitigation: none in code." The owner closes Obsidian, and the `Plan.hashes` check covers drift before the run. The PRD requires `atomic_write_bytes` for all writes, so a no-clobber write primitive is out of scope.
- Fixed blocker (directories named `*.md`): `occupied_stems` holds every entry, and reads are limited to regular files.
- Fixed blocker (the inverse check rejects a file with both `[[old]]` and `[[new]]`): the stems of existing link targets are now occupied, so no new stem can equal a target that is already linked. The check stays as a backstop.
- Fixed blocker (fences in list items): `_CONTAINER` accepts a list marker. Recorded as non-blocker: an unclosed blockquote fence protects to end of file, which keeps more text unchanged and never corrupts.
- Downgraded to non-blocker (pattern disagreements): `\[[old]]` and `[[old|` are rewritten as text, which is harmless and byte-reversible. The `leftover_pattern` hit on a folder component fails before any write. Digit stems have no case.
- Fixed blocker (leftover scope): `.md` files outside `notes/` are scanned read-only and reported as `ApplyResult.outside_references`. They are never rewritten, because the PRD forbids changing templates.
- Fixed blocker (block-scalar `type`): `TYPE_BLOCK` skips a note whose type cannot be read from one line (`REASON_TYPE_UNKNOWN`).
- Fixed blocker (map validation, `Path + str`): undo step 1 validates the whole map (types, `run_id`, hashes, unique paths). The map name is built from `run_id`.
- Fixed non-blocker (garbage dates counted as date-only): date-only now requires `date.fromisoformat` to succeed, and other values are `REASON_UNPARSEABLE`.
- Question (answered in Mapping rules): per-file records carry duplicate old ids.
