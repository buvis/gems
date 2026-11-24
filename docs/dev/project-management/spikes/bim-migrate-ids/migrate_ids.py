"""Migrate bim zettel ids from local wall-clock time to UTC (spike, PRD 00162).

Design: docs/dev/project-management/designs/00162-bim-migrate-ids-to-utc-v1-design.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

from buvis.pybase.filesystem import atomic_write_bytes

DEFAULT_ZONE = "Europe/Prague"
SUFFIX_SECONDS = range(60, 100)  # 60..99 inclusive
MAP_VERSION = 1
TEMP_SUFFIX = ".migrating"  # temp file name: f"{path.name}.{run_id}{TEMP_SUFFIX}"

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

# Frontmatter is edited as bytes, never as YAML.
_EOL = rb"[ \t]*(?:[ \t]#[^\r\n]*)?\r?$"  # trailing blanks, optional YAML comment, CR
FRONTMATTER = re.compile(rb"\A---\r?\n(.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.S)
ID_LINE = re.compile(rb"^id:[ \t]*([\"']?)(\d{14}|\d{12})\1" + _EOL, re.M)
TYPE_DOCUMENT = re.compile(rb"^type:[ \t]*([\"']?)document\1" + _EOL, re.M)
DATE_LINE = re.compile(rb"^date:[ \t]*([\"']?)(.*?)\1" + _EOL, re.M)
_CONTAINER = rb"[ \t]*(?:>[ \t]?)*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)?"  # blockquote and list-item prefixes
_CLOSER = rb"[ \t]*(?:>[ \t]?)*"
FENCE = re.compile(
    rb"^" + _CONTAINER + rb"(`{3,})[^\n]*\n.*?(?:^" + _CLOSER + rb"\1`*[ \t]*\r?$|\Z)"
    rb"|^" + _CONTAINER + rb"(~{3,})[^\n]*\n.*?(?:^" + _CLOSER + rb"\2~*[ \t]*\r?$|\Z)",
    re.S | re.M,
)
TYPE_BLOCK = re.compile(rb"^type:[ \t]*(?:[|>][^\r\n]*)?\r?$", re.M)  # type with no value on its line
INLINE_CODE = re.compile(rb"(?<!`)(`+)(?!`)(?:(?!\n[ \t]*\r?\n).)*?(?<!`)\1(?!`)", re.S)
_WIKILINK_TARGET = re.compile(rb"\[\[([^\[\]|#\n]*)")
_EXCLUDED_DIRS = {".obsidian", ".trash"}


@dataclass(frozen=True)
class NoteChange:
    path: Path  # absolute old path
    new_path: Path  # absolute; equals path when the stem does not start with the old id or the id is unchanged
    old_id: str
    new_id: str  # equals old_id for an "already on UTC" note
    old_date_line: str | None  # decoded line without line ending; None when the note had no date line
    new_date_line: str
    date_changed: bool


@dataclass(frozen=True)
class Skip:
    path: Path
    reason: str  # one REASON_* constant


@dataclass(frozen=True)
class Plan:
    vault: Path  # resolved
    naive_timezone: str
    changes: tuple[NoteChange, ...]  # notes whose id, file name or date line change, sorted by (old_id, path)
    skips: tuple[Skip, ...]
    already_utc: tuple[Path, ...]  # new_id == old_id (date line may still change)
    local_digit_mismatch: tuple[Path, ...]  # old id (12 digits padded "00") != wall-clock digits of the resolved date
    kept_attachments: tuple[Path, ...]  # non-.md files under notes/ whose stem starts with a migrating old id
    reference_count: int  # references the apply will rewrite
    hashes: Mapping[Path, str]  # sha256 hex of every .md under notes/ as read by the plan


class MigrationError(Exception):
    """Any premise or apply failure; the message names the file."""

    def __init__(self, message: str, map_file: Path | None = None) -> None:
        super().__init__(message)
        self.map_file = map_file  # set for every error raised after apply step 4


@dataclass(frozen=True)
class ApplyResult:
    map_file: Path
    outside_references: tuple[Path, ...]  # .md files outside notes/ that link to an old stem; not rewritten


@dataclass(frozen=True)
class UndoReport:
    restored: tuple[Path, ...]
    unchanged: tuple[Path, ...]
    skipped: tuple[Path, ...]  # changed since apply; left untouched


@dataclass(frozen=True)
class _Note:
    """A note whose date resolved; the plan maps it or keeps its id."""

    path: Path
    old_id: str
    aware: datetime
    date_changed: bool
    old_line: str | None
    new_line: str

    @property
    def base(self) -> str:
        return self.aware.astimezone(UTC).strftime("%Y%m%d%H%M%S")

    @property
    def rest(self) -> str | None:
        """Stem tail after the old id when the stem starts with the id as a token, else None."""
        stem = self.path.stem
        if stem.startswith(self.old_id) and not stem[len(self.old_id) : len(self.old_id) + 1].isdigit():
            return stem[len(self.old_id) :]
        return None


# --- protected spans and references -------------------------------------------


def protected_spans(data: bytes) -> list[tuple[int, int]]:
    """Fence spans first (a closer may be longer than the opener; a fence may
    sit in a blockquote; an unclosed fence runs to end of file), then
    INLINE_CODE spans searched only in the gaps between fences, so an inline
    backtick never pairs across a fence."""
    spans: list[tuple[int, int]] = []
    start = 0
    for fence in [*FENCE.finditer(data), None]:
        end = fence.start() if fence else len(data)
        spans.extend(m.span() for m in INLINE_CODE.finditer(data, start, end))
        if fence:
            spans.append(fence.span())
            start = fence.end()
    return spans


def _unprotected(data: bytes) -> list[tuple[int, int]]:
    gaps, pos = [], 0
    for start, end in protected_spans(data):
        gaps.append((pos, start))
        pos = end
    gaps.append((pos, len(data)))
    return gaps


def stem_pattern(stems: Iterable[str]) -> re.Pattern[bytes]:
    """[[ + optional folder path ending in / + one stem + optional .md, then | or # or ]]."""
    alts = b"|".join(re.escape(stem.encode()) for stem in sorted(stems, key=len, reverse=True))
    return re.compile(rb"(\[\[(?:[^\[\]|#\n]*/)?)(" + alts + rb")(?=(?:\.md)?(?:\\?\||#|\]\]))")


def rewrite_references(data: bytes, pattern: re.Pattern[bytes], stem_map: Mapping[str, str]) -> tuple[bytes, int]:
    """One pass over the unprotected spans; returns new bytes and the count of rewritten references."""
    parts: list[bytes] = []
    count = pos = 0
    for start, end in _unprotected(data):
        new, n = pattern.subn(lambda m: m.group(1) + stem_map[m.group(2).decode()].encode(), data[start:end])
        parts += [data[pos:start], new]
        count += n
        pos = end
    return b"".join(parts), count


def _link_targets(blobs: Iterable[bytes]) -> set[str]:
    """Casefolded last path component of every wikilink target in unprotected spans."""
    targets = set()
    for data in blobs:
        for start, end in _unprotected(data):
            for m in _WIKILINK_TARGET.finditer(data, start, end):
                target = m.group(1).removesuffix(b"\\").removesuffix(b".md").rsplit(b"/", 1)[-1]
                targets.add(target.decode(errors="replace").casefold())
    return targets


# --- time zone resolution ------------------------------------------------------


def localize(naive: datetime, zone: ZoneInfo) -> datetime | str:
    a = naive.replace(tzinfo=zone, fold=0)
    b = naive.replace(tzinfo=zone, fold=1)
    if a.utcoffset() == b.utcoffset():
        return a
    if a.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive:
        return REASON_NONEXISTENT
    return REASON_AMBIGUOUS


def resolve_date(value: str, zone: ZoneInfo) -> tuple[datetime, bool] | str:
    """Return (aware date, date_changed) or a REASON_* string."""
    if not re.search(r"\d[T ]\d", value):
        try:
            date.fromisoformat(value)
        except ValueError:
            return REASON_UNPARSEABLE
        return REASON_DATE_ONLY
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return REASON_UNPARSEABLE
    try:
        if parsed.tzinfo is not None:
            parsed.astimezone(UTC)
            return parsed, False
        aware = localize(parsed, zone)
        if isinstance(aware, str):
            return aware
        aware.astimezone(UTC)
    except OverflowError:
        return REASON_UNPARSEABLE
    return aware, True


def _from_date_line(m: re.Match[bytes], zone: ZoneInfo) -> tuple[datetime, bool, str | None, str] | str:
    resolved = resolve_date(m.group(2).decode(), zone)
    if isinstance(resolved, str):
        return resolved
    aware, changed = resolved
    line = m.group(0).decode().removesuffix("\r")
    if not changed:
        return aware, False, line, line
    offset = aware.replace(microsecond=0).isoformat()[19:].encode()
    new = m.string[m.start() : m.end(2)] + offset + m.string[m.end(2) : m.end()]
    return aware, True, line, new.decode().removesuffix("\r")


def _from_old_id(old_id: str, zone: ZoneInfo) -> tuple[datetime, bool, str | None, str] | str:
    try:
        naive = datetime.strptime(old_id.ljust(14, "0"), "%Y%m%d%H%M%S")
    except ValueError:
        return REASON_BAD_ID_TIME
    aware = localize(naive, zone)
    if isinstance(aware, str):
        return aware
    return aware, True, None, "date: " + aware.isoformat()


def _resolve_note(path: Path, data: bytes, fm: re.Match[bytes], old_id: str, zone: ZoneInfo) -> _Note | Skip | None:
    """None for a document zettel; a Skip when the note keeps its id; else the resolved note."""
    span = fm.start(), fm.end()
    if TYPE_BLOCK.search(data, *span):
        return Skip(path, REASON_TYPE_UNKNOWN)
    if TYPE_DOCUMENT.search(data, *span):
        return None
    try:
        data[span[0] : span[1]].decode()
    except UnicodeDecodeError:
        return Skip(path, REASON_NOT_UTF8)
    date_m = DATE_LINE.search(data, *span)
    resolved = _from_date_line(date_m, zone) if date_m else _from_old_id(old_id, zone)
    if isinstance(resolved, str):
        return Skip(path, resolved)
    return _Note(path, old_id, *resolved)


# --- planning --------------------------------------------------------------------


def _read_notes(notes_dir: Path) -> tuple[dict[Path, bytes], list[Skip]]:
    files: dict[Path, bytes] = {}
    skips: list[Skip] = []
    for path in sorted(notes_dir.rglob("*.md")):
        if path.is_symlink():
            skips.append(Skip(path, REASON_SYMLINK))
        elif path.is_file():
            files[path] = path.read_bytes()
    return files, skips


def _select(files: Mapping[Path, bytes], zone: ZoneInfo, skips: list[Skip]) -> tuple[list[_Note], set[str]]:
    """Resolve every note; return the resolved notes and the ids that are kept."""
    notes: list[_Note] = []
    taken: set[str] = set()
    for path, data in files.items():
        fm = FRONTMATTER.match(data)
        id_m = ID_LINE.search(data, fm.start(), fm.end()) if fm else None
        if fm is None or id_m is None:
            continue
        old_id = id_m.group(2).decode()
        result = _resolve_note(path, data, fm, old_id, zone)
        if isinstance(result, _Note):
            notes.append(result)
            continue
        taken.add(old_id)
        if result is not None:
            skips.append(result)
    return notes, taken


def _free_id(note: _Note, ids: set[str], stems: set[str]) -> str | None:
    rest = note.rest
    for candidate in [note.base, *(note.base[:12] + f"{s:02d}" for s in SUFFIX_SECONDS)]:
        if candidate in ids or (rest is not None and (candidate + rest).casefold() in stems):
            continue
        return candidate
    return None


def _assign_ids(moving: list[_Note], taken: set[str], occupied: set[str]) -> tuple[dict[Path, str], list[_Note]]:
    """Pick new ids in order; a note with no free id keeps its id and stem, then the loop reruns."""
    kept: list[_Note] = []
    while True:
        ids = taken | {n.old_id for n in kept}
        stems = occupied | {n.path.stem.casefold() for n in kept}
        kept_paths = {n.path for n in kept}
        chosen: dict[Path, str] = {}
        new_kept: list[_Note] = []
        for note in moving:
            if note.path in kept_paths:
                continue
            new_id = _free_id(note, ids, stems)
            if new_id is None:
                new_kept.append(note)
                continue
            chosen[note.path] = new_id
            ids.add(new_id)
            if note.rest is not None:
                stems.add((new_id + note.rest).casefold())
        if not new_kept:
            return chosen, kept
        kept += new_kept


def _change(note: _Note, new_id: str) -> NoteChange:
    rest = note.rest
    new_path = note.path.with_name(new_id + rest + note.path.suffix) if rest is not None else note.path
    return NoteChange(note.path, new_path, note.old_id, new_id, note.old_line, note.new_line, note.date_changed)


def _vault_entries(vault: Path) -> list[Path]:
    return [p for p in vault.rglob("*") if not _EXCLUDED_DIRS & set(p.relative_to(vault).parts)]


def _reference_count(files: Mapping[Path, bytes], changes: list[NoteChange]) -> int:
    stem_map = {c.path.stem: c.new_path.stem for c in changes if c.new_path != c.path}
    if not stem_map:
        return 0
    pattern = stem_pattern(stem_map)
    return sum(rewrite_references(data, pattern, stem_map)[1] for data in files.values())


def plan_migration(vault: Path, naive_timezone: str = DEFAULT_ZONE) -> Plan:
    vault = vault.resolve()
    notes_dir = vault / "notes"
    if notes_dir.is_symlink() or not notes_dir.is_dir():
        raise MigrationError(f"{notes_dir} is not a directory")
    files, skips = _read_notes(notes_dir)
    notes, taken = _select(files, ZoneInfo(naive_timezone), skips)
    entries = _vault_entries(vault)
    md_stems = Counter(p.stem.casefold() for p in entries if p.suffix == ".md" and (p.is_symlink() or p.is_file()))
    moving: list[_Note] = []
    already: list[_Note] = []
    for note in notes:
        if note.base == note.old_id:
            already.append(note)
        elif note.rest is not None and md_stems[note.path.stem.casefold()] > 1:
            skips.append(Skip(note.path, REASON_STEM_SHARED))
        else:
            moving.append(note)
            continue
        taken.add(note.old_id)
    renaming = {n.path for n in moving if n.rest is not None}
    occupied = {p.stem.casefold() for p in entries if p not in renaming}
    occupied |= _link_targets(files.values()) - {p.stem.casefold() for p in renaming}
    new_ids, kept = _assign_ids(sorted(moving, key=lambda n: (n.old_id, n.path)), taken, occupied)
    skips += [Skip(n.path, REASON_NO_SUFFIX) for n in kept]
    changes = [_change(n, n.old_id) for n in already if n.date_changed]
    changes += [_change(n, new_ids[n.path]) for n in moving if n.path in new_ids]
    changes.sort(key=lambda c: (c.old_id, c.path))
    migrating = tuple(c.old_id for c in changes if c.new_id != c.old_id)
    return Plan(
        vault=vault,
        naive_timezone=naive_timezone,
        changes=tuple(changes),
        skips=tuple(sorted(skips, key=lambda s: s.path)),
        already_utc=tuple(n.path for n in already),
        local_digit_mismatch=tuple(
            n.path for n in notes if n.old_id.ljust(14, "0") != n.aware.strftime("%Y%m%d%H%M%S")
        ),
        kept_attachments=tuple(
            p
            for p in sorted(entries)
            if p.is_relative_to(notes_dir) and p.suffix != ".md" and p.is_file() and p.stem.startswith(migrating)
        ),
        reference_count=_reference_count(files, changes),
        hashes={path: hashlib.sha256(data).hexdigest() for path, data in files.items()},
    )


# --- shared by apply and undo ----------------------------------------------------


def leftover_pattern(stems: Iterable[str]) -> re.Pattern[bytes]:
    """Looser than stem_pattern: an old stem as a token in a link target, not an attachment."""
    alts = b"|".join(re.escape(stem.encode()) for stem in sorted(stems, key=len, reverse=True))
    return re.compile(
        rb"\[\[[^\]|#\n\\]*?(?<![0-9A-Za-z_-])(" + alts + rb")"
        rb"(?![0-9A-Za-z_-])(?!\.(?!md(?![0-9A-Za-z]))[0-9A-Za-z])[^\]|#\n\\]*(?:\\?\||#|\]\])"
    )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hits(files: Mapping[Path, bytes], pattern: re.Pattern[bytes]) -> list[Path]:
    """Files with a pattern match in an unprotected span."""
    return [p for p, data in files.items() if any(pattern.search(data, a, b) for a, b in _unprotected(data))]


def _rewriter(stem_map: Mapping[str, str]) -> Callable[[bytes], bytes]:
    if not stem_map:
        return lambda data: data
    pattern = stem_pattern(stem_map)
    return lambda data: rewrite_references(data, pattern, stem_map)[0]


def _edit_note(data: bytes, to_id: str, from_line: str | None, to_line: str | None) -> bytes:
    """Set the frontmatter id to to_id and turn date line from_line into to_line (None: no date line)."""
    span = FRONTMATTER.match(data).span()
    if from_line is None and to_line is not None:  # insert after the id line, with its line ending
        id_m = ID_LINE.search(data, *span)
        at = id_m.end() + 1
        eol = b"\r\n" if id_m.group(0).endswith(b"\r") else b"\n"
        data = data[:at] + to_line.encode() + eol + data[at:]
    elif from_line is not None and from_line != to_line:
        start = DATE_LINE.search(data, *span).start()
        end = start + len(from_line.encode())
        if to_line is None:  # drop the line with its line ending
            end = data.index(b"\n", end) + 1
        data = data[:start] + (to_line or "").encode() + data[end:]
    id_m = ID_LINE.search(data, *FRONTMATTER.match(data).span())
    return data[: id_m.start(2)] + to_id.encode() + data[id_m.end(2) :]


def _reverse(data: bytes, inverse: Callable[[bytes], bytes], note: tuple[str, str | None, str] | None) -> bytes:
    """Inverse reference rewrite, then the inverse note edits; note = (old_id, old_date_line, new_date_line)."""
    data = inverse(data)
    return _edit_note(data, note[0], note[2], note[1]) if note else data


@dataclass(frozen=True)
class _Op:
    """Phase A moves stage[0] to stage[1]; phase B writes data to dest, then removes the paths in remove."""

    dest: Path
    data: bytes
    renamed: bool  # dest is not the path the file had when the run started
    stage: tuple[Path, Path] | None = None
    remove: tuple[Path, ...] = ()


def _execute(ops: list[_Op], map_file: Path | None, remove: Iterable[Path] = ()) -> None:
    """Stage every moved source to its temp, then write every dest; an OSError becomes MigrationError."""
    vacated: set[Path] = set()
    current: Path | None = None
    try:
        for op in ops:
            if op.stage:
                source, current = op.stage
                if current.exists():
                    raise MigrationError(f"{current}: temp file exists", map_file)
                os.rename(source, current)
                vacated.add(source)
        for op in ops:
            current = op.dest
            if op.renamed and op.dest.exists() and op.dest not in vacated:
                raise MigrationError(f"{op.dest}: target exists", map_file)
            atomic_write_bytes(op.dest, op.data)
            for current in op.remove:
                current.unlink()
        for current in remove:
            current.unlink()
    except OSError as exc:
        raise MigrationError(f"{current}: {exc}", map_file) from exc


# --- apply -------------------------------------------------------------------------


@dataclass(frozen=True)
class _Kept:
    """A file the apply rewrites or renames."""

    path: Path
    new_path: Path
    change: NoteChange | None
    before: bytes
    after: bytes


def _prepare(plan: Plan, stem_map: Mapping[str, str]) -> list[_Kept]:
    """After bytes of every changed file; refuses drift since the plan."""
    files, _ = _read_notes(plan.vault / "notes")
    hashes = {path: _sha(data) for path, data in files.items()}
    drift = sorted(p for p in hashes.keys() | plan.hashes.keys() if hashes.get(p) != plan.hashes.get(p))
    if drift:
        raise MigrationError("changed since the plan: " + ", ".join(str(p) for p in drift))
    changes = {c.path: c for c in plan.changes}
    rewrite = _rewriter(stem_map)
    kept = []
    for path, before in files.items():
        c = changes.get(path)
        after = rewrite(_edit_note(before, c.new_id, c.old_date_line, c.new_date_line) if c else before)
        new_path = c.new_path if c else path
        if after != before or new_path != path:
            kept.append(_Kept(path, new_path, c, before, after))
    return kept


def _refuse_leftovers(files: Mapping[Path, bytes], stems: set[str], map_file: Path | None) -> None:
    hits = _hits(files, leftover_pattern(stems)) if stems else []
    if hits:
        raise MigrationError("links to an old id left in: " + ", ".join(str(p) for p in hits), map_file)


def _check_reversible(kept: list[_Kept], stem_map: Mapping[str, str]) -> None:
    inverse = _rewriter({new: old for old, new in stem_map.items()})
    for k in kept:
        c = k.change
        if _reverse(k.after, inverse, (c.old_id, c.old_date_line, c.new_date_line) if c else None) != k.before:
            raise MigrationError(f"{k.path}: the rewrite cannot be undone (does it link a new id already?)")


def _outside_references(vault: Path, stems: list[str]) -> list[Path]:
    """.md files outside notes/ that link an old stem; read only."""
    if not stems:
        return []
    notes = vault / "notes"
    md = [p for p in sorted(_vault_entries(vault)) if p.suffix == ".md" and p.is_file() and not p.is_relative_to(notes)]
    return _hits({p: p.read_bytes() for p in md}, stem_pattern(stems))


def _apply_temp(path: Path, run_id: str) -> Path:
    return path.with_name(f"{path.name}.{run_id}{TEMP_SUFFIX}")


def _write_map(plan: Plan, map_file: Path, kept: list[_Kept]) -> Path:
    def rel(path: Path) -> str:
        return path.relative_to(plan.vault).as_posix()

    files = []
    for k in kept:
        c = k.change
        note = (c.old_id, c.new_id, c.old_date_line, c.new_date_line) if c else (None,) * 4
        entry = {"old_path": rel(k.path), "new_path": rel(k.new_path), "sha256_before": _sha(k.before)}
        entry |= {"sha256_after": _sha(k.after), "temp_path": None}
        if k.path != k.new_path:
            entry["temp_path"] = rel(_apply_temp(k.path, map_file.stem))
        files.append(entry | dict(zip(("old_id", "new_id", "old_date_line", "new_date_line"), note, strict=True)))
    data = {"version": MAP_VERSION, "vault": str(plan.vault), "run_id": map_file.stem}
    data |= {"naive_timezone": plan.naive_timezone, "files": files}
    map_file.parent.mkdir(parents=True, exist_ok=True)
    if map_file.exists():
        raise MigrationError(f"{map_file}: map file exists")
    atomic_write_bytes(map_file, (json.dumps(data, indent=2, sort_keys=True) + "\n").encode())
    return map_file


def apply_migration(plan: Plan, map_dir: Path, *, now: datetime | None = None) -> ApplyResult:
    map_dir = map_dir.resolve()
    if map_dir.is_relative_to(plan.vault):
        raise MigrationError(f"map dir {map_dir} is inside the vault {plan.vault}")
    stem_map = {c.path.stem: c.new_path.stem for c in plan.changes if c.new_path != c.path}
    leftover = set(stem_map) - set(stem_map.values())
    map_file = None
    try:
        kept = _prepare(plan, stem_map)
        _refuse_leftovers({k.path: k.after for k in kept}, leftover, None)
        _check_reversible(kept, stem_map)
        outside = _outside_references(plan.vault, list(stem_map))
        for path in outside:
            print(f"warning: {path} links an old id; it is not rewritten", file=sys.stderr)
        run_id = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
        map_file = _write_map(plan, map_dir / f"{run_id}.json", kept)
        ops = []
        for k in kept:
            temp = _apply_temp(k.path, run_id) if k.path != k.new_path else None
            ops.append(_Op(k.new_path, k.after, temp is not None, temp and (k.path, temp), (temp,) if temp else ()))
        _execute(ops, map_file)
        _refuse_leftovers(_read_notes(plan.vault / "notes")[0], leftover, map_file)
    except OSError as exc:
        raise MigrationError(f"{exc.filename}: {exc}", map_file) from exc
    return ApplyResult(map_file, tuple(outside))


# --- undo --------------------------------------------------------------------------

_HEX = re.compile(r"[0-9a-f]{64}")
_RUN_ID = re.compile(r"\d{8}T\d{6}Z")
_MAP_SCHEMA = {"version": (int,), "vault": (str,), "run_id": (str,), "naive_timezone": (str,), "files": (list,)}
_RECORD_SCHEMA = dict.fromkeys(("old_path", "new_path", "sha256_before", "sha256_after"), (str,)) | dict.fromkeys(
    ("temp_path", "old_id", "new_id", "old_date_line", "new_date_line"), (str, type(None))
)


def _typed(obj: object, schema: Mapping[str, tuple[type, ...]]) -> bool:
    return isinstance(obj, dict) and all(k in obj and isinstance(obj[k], t) for k, t in schema.items())


def _check_record(rec: object, notes: Path, map_file: Path) -> None:
    ok = _typed(rec, _RECORD_SCHEMA) and all(_HEX.fullmatch(rec[k]) for k in ("sha256_before", "sha256_after"))
    for key in ("old_path", "new_path", "temp_path"):
        value = rec[key] if ok else None
        if value is not None:
            pure = PurePosixPath(value)
            inside = (notes.parent / value).resolve().is_relative_to(notes)
            ok = not pure.is_absolute() and ".." not in pure.parts and inside
    if not ok:
        raise MigrationError(f"{map_file}: bad record {rec!r}")


def _load_map(vault: Path, map_file: Path) -> dict:
    try:
        data = json.loads(map_file.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise MigrationError(f"{map_file}: cannot read the map: {exc}") from exc
    if not _typed(data, _MAP_SCHEMA) or data["version"] != MAP_VERSION or not _RUN_ID.fullmatch(data["run_id"]):
        raise MigrationError(f"{map_file}: not a version {MAP_VERSION} migration map")
    if data["vault"] != str(vault):
        raise MigrationError(f"{map_file}: the map is for vault {data['vault']}, not {vault}")
    notes = vault / "notes"
    if notes.is_symlink():
        raise MigrationError(f"{notes} is a symlink")
    for rec in data["files"]:
        _check_record(rec, notes, map_file)
    for key in ("old_path", "new_path"):
        if len({rec[key] for rec in data["files"]}) != len(data["files"]):
            raise MigrationError(f"{map_file}: two records share a {key}")
    return data


@dataclass(frozen=True)
class _Entry:
    """One map record with absolute paths."""

    old: Path
    new: Path
    temp: Path | None
    undo_temp: Path
    before: str
    after: str
    note: tuple[str, str | None, str] | None  # old_id, old_date_line, new_date_line


def _entry(vault: Path, run_id: str, rec: Mapping) -> _Entry:
    new = vault / rec["new_path"]
    return _Entry(
        old=vault / rec["old_path"],
        new=new,
        temp=vault / rec["temp_path"] if rec["temp_path"] else None,
        undo_temp=new.with_name(f"{new.name}.undo-{run_id}{TEMP_SUFFIX}"),
        before=rec["sha256_before"],
        after=rec["sha256_after"],
        note=(rec["old_id"], rec["old_date_line"], rec["new_date_line"]) if rec["old_id"] is not None else None,
    )


@dataclass(frozen=True)
class _State:
    kind: str  # "unchanged", "restore" (reverse the source), "temp" (source holds the old bytes), "skip"
    source: Path | None
    data: bytes | None  # bytes of the file where the entry sits now
    cleanup: tuple[Path, ...]  # tool temps to remove


def _read(path: Path | None) -> bytes | None:
    return path.read_bytes() if path is not None and path.is_file() else None


def _classify(e: _Entry, owner_before: str | None) -> _State:
    """The first rule that holds, from the bytes on disk."""
    old, new, undo, temp = _read(e.old), _read(e.new), _read(e.undo_temp), _read(e.temp)
    temp_done = (e.temp,) if temp is not None and _sha(temp) == e.before else ()
    if old is not None and _sha(old) == e.before:
        undo_done = (e.undo_temp,) if undo is not None and _sha(undo) == e.after else ()
        return _State("unchanged", None, old, temp_done + undo_done)
    if new is not None and _sha(new) == e.after:
        return _State("restore", e.new, new, temp_done)
    if undo is not None and _sha(undo) == e.after:
        return _State("restore", e.undo_temp, undo, temp_done)
    if new is not None and _sha(new) != owner_before:
        return _State("skip", None, new, ())
    if temp_done:
        return _State("temp", e.temp, temp, temp_done)
    return _State("skip", None, None, ())


def _linked(targets: Mapping[str, int], blobs: Iterable[bytes | None]) -> set[int]:
    """Indices of the targets whose stem a blob links, in unprotected spans."""
    if not targets:
        return set()
    pattern = stem_pattern(targets)
    return {
        targets[m.group(2).decode()]
        for data in blobs
        if data
        for a, b in _unprotected(data)
        for m in pattern.finditer(data, a, b)
    }


def _settle(entries: list[_Entry], states: list[_State]) -> tuple[list[int], dict[int, bytes]]:
    """Skip fixpoint; returns the entries to restore and their old bytes."""
    skipped = {i for i, s in enumerate(states) if s.kind == "skip"}
    while True:
        live = [i for i, e in enumerate(entries) if i not in skipped and e.old != e.new]
        inverse = _rewriter({entries[i].new.stem: entries[i].old.stem for i in live})
        restoring = [i for i, s in enumerate(states) if s.kind in ("restore", "temp") and i not in skipped]
        out = {
            i: states[i].data if states[i].kind == "temp" else _reverse(states[i].data, inverse, entries[i].note)
            for i in restoring
        }
        add = {i for i in restoring if _sha(out[i]) != entries[i].before}
        targets = {entries[i].new.stem: i for i in restoring if i in live}
        # only skipped files keep their after-state links; unchanged files still link old stems
        blobs = [s.data for i, s in enumerate(states) if i in skipped]
        add |= _linked(targets, blobs)
        staged = {entries[i].new for i in targets.values() if states[i].source == entries[i].new}
        add |= {i for i in targets.values() if entries[i].old.exists() and entries[i].old not in staged}
        if not add:
            return restoring, out
        skipped |= add


def _undo_op(e: _Entry, s: _State, data: bytes) -> _Op:
    stage = (e.new, e.undo_temp) if s.source == e.new and e.old != e.new else None
    via_undo_temp = stage is not None or s.source == e.undo_temp
    return _Op(e.old, data, e.old != e.new, stage, ((e.undo_temp,) if via_undo_temp else ()) + s.cleanup)


def undo_migration(vault: Path, map_file: Path) -> UndoReport:
    vault = vault.resolve()
    data = _load_map(vault, map_file)
    entries = [_entry(vault, data["run_id"], rec) for rec in data["files"]]
    owners = {e.old: e.before for e in entries}
    try:
        states = [_classify(e, owners.get(e.new)) for e in entries]
    except OSError as exc:
        raise MigrationError(f"{exc.filename}: {exc}") from exc
    restoring, out = _settle(entries, states)
    unchanged = [i for i, s in enumerate(states) if s.kind == "unchanged"]
    _execute(
        [_undo_op(entries[i], states[i], out[i]) for i in restoring],
        map_file,
        [p for i in unchanged for p in states[i].cleanup],
    )
    return UndoReport(
        restored=tuple(entries[i].old for i in restoring),
        unchanged=tuple(entries[i].old for i in unchanged),
        skipped=tuple(e.new for i, e in enumerate(entries) if i not in restoring and i not in unchanged),
    )


# --- command line ------------------------------------------------------------------


def default_map_dir() -> Path:
    """$XDG_STATE_HOME/bim/migrate-ids, or ~/.local/state/bim/migrate-ids when it is unset or empty."""
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "bim" / "migrate-ids"


def main(argv: list[str] | None = None) -> int:
    """Dry run: print the plan of the vault given with --vault."""
    parser = argparse.ArgumentParser(description="Migrate bim zettel ids from local time to UTC.")
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--naive-timezone", default=DEFAULT_ZONE)
    args = parser.parse_args(argv)
    plan = plan_migration(args.vault, args.naive_timezone)
    for c in plan.changes:
        old, new = c.path.relative_to(plan.vault), c.new_path.relative_to(plan.vault)
        print(f"{old} -> {new}  {c.old_id} -> {c.new_id}")
    print(
        f"{len(plan.changes)} changes, {len(plan.skips)} skips, {len(plan.already_utc)} already on UTC, "
        f"{plan.reference_count} references"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
