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
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
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
