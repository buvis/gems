"""Tiromex mechanical validator: per-note rules and the graph rules over the folder.

Pure: no console, no Click. Every rule returns :class:`Diagnostic` objects with a
stable ``rule`` id, so a test can assert that a fixture broken in one way gives
exactly its own rule and no other.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from .format import (
    ASSENT_VALUES,
    CLAIM_BEARING_CONCEPT_TYPES,
    CONCEPT_NOTE_TYPES,
    CONCEPT_TYPE_VALUES,
    DOUBT_MODE_VALUES,
    FORBIDDEN_TAGS,
    LIFECYCLE_VALUES,
    MEMBERS_CLOSE,
    MEMBERS_OPEN,
    MIRROR_PREFIX,
    TRANSITIVE_RELATIONS,
    ConceptType,
    DoubtMode,
    NoteKind,
    Relation,
    as_datetime,
    body_lines,
    h1_titles,
    link_file,
    parents,
    parse_links,
    read_note,
    relations,
    sources,
)
from .paths import confine, iter_note_files, to_vault_rel

if TYPE_CHECKING:
    from .format import TxNote
    from .paths import TiromexPaths

__all__ = ["Diagnostic", "validate_note", "validate_tiromex"]

_ZETTEL_ID = re.compile(r"[0-9]{14}")
_TIMESTAMP = "%Y%m%d%H%M%S"
_REQUIRED_FIELDS = ("id", "title", "date", "type")
_LINK_KEYS = (*(rel.value for rel in Relation), "parent")
_INDEX_TITLE_PREFIX = "§ "
_MAX_CLAIMS = 3


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One validation failure.

    Attributes:
        path: The vault-relative path of the note.
        rule: A stable rule id, e.g. ``required-field``.
        message: A human-readable explanation.
        line: The 1-based line where derivable, else ``None``.
    """

    path: str
    rule: str
    message: str
    line: int | None = None


def _present(value: object) -> bool:
    return value is not None and not (isinstance(value, str) and not value.strip())


def _in(value: object, allowed: frozenset[str]) -> bool:
    return isinstance(value, str) and value in allowed


def _check_required(note: TxNote) -> list[Diagnostic]:
    meta = note.data.metadata
    return [
        Diagnostic(note.path, "required-field", f"missing required field {name!r}")
        for name in _REQUIRED_FIELDS
        if not _present(meta.get(name))
    ]


def _check_publish_and_tags(note: TxNote) -> list[Diagnostic]:
    meta = note.data.metadata
    found: list[Diagnostic] = []
    if meta.get("publish") is True:
        found.append(Diagnostic(note.path, "publish-true", "publish must never be true"))
    tags = meta.get("tags")
    for tag in tags if isinstance(tags, list) else []:
        if isinstance(tag, str) and ":" in tag:
            found.append(Diagnostic(note.path, "legacy-colon-tag", f"colon-prefixed legacy tag: {tag!r}"))
        if _in(tag, FORBIDDEN_TAGS):
            found.append(Diagnostic(note.path, "forbidden-tag", f"tag {tag!r} is not allowed"))
    return found


def _check_h1(note: TxNote) -> list[Diagnostic]:
    titles = h1_titles(note.body)
    if len(titles) != 1:
        return [Diagnostic(note.path, "h1-exactly-one", f"body must have exactly one H1, found {len(titles)}")]
    title = note.data.metadata.get("title")
    if _present(title) and titles[0] != str(title):
        return [Diagnostic(note.path, "h1-title-mismatch", f"H1 {titles[0]!r} does not equal title {str(title)!r}")]
    return []


def _check_id(note: TxNote) -> list[Diagnostic]:
    meta = note.data.metadata
    if not _present(meta.get("id")):
        return []
    note_id = str(meta["id"])
    found: list[Diagnostic] = []
    well_formed = _ZETTEL_ID.fullmatch(note_id) is not None
    if not well_formed:
        found.append(Diagnostic(note.path, "zettel-id-format", f"id must be exactly 14 digits, got {note_id!r}"))
    stem = PurePosixPath(note.path).stem
    if note_id != stem:
        found.append(Diagnostic(note.path, "id-filename-mismatch", f"id {note_id!r} must equal the file stem {stem!r}"))
    created = as_datetime(meta.get("date"))
    if well_formed and created is not None:
        accepted = {created.strftime(_TIMESTAMP), created.astimezone().strftime(_TIMESTAMP)}
        if note_id not in accepted:
            message = f"date {created.isoformat()} does not agree with id {note_id!r} to the second"
            found.append(Diagnostic(note.path, "id-created-mismatch", message))
    return found


def _check_body(note: TxNote, max_body_lines: int) -> list[Diagnostic]:
    lines = body_lines(note.body)
    found: list[Diagnostic] = []
    if all(h1_titles(line) for line in lines):
        found.append(Diagnostic(note.path, "empty-body", "body holds no line under its H1"))
    if len(lines) > max_body_lines:
        message = f"body has {len(lines)} non-blank lines, exceeds max {max_body_lines}"
        found.append(Diagnostic(note.path, "oversized-body", message))
    return found


def _check_links(note: TxNote) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for key in _LINK_KEYS:
        if key not in note.data.reference:
            continue
        links = parse_links(note.data.reference[key])
        if not links:
            found.append(Diagnostic(note.path, "link-shape", f"{key} holds no wikilink"))
        for link in links:
            if not link.title.strip() or link.target.endswith(".md") or "#" in link.target:
                message = f"{key} link [[{link.target}|{link.title}]] needs a title and a target without .md or #"
                found.append(Diagnostic(note.path, "link-shape", message))
    return found


def _check_review(note: TxNote) -> list[Diagnostic]:
    reviewed = as_datetime(note.data.metadata.get("reviewed"))
    updated = as_datetime(note.data.metadata.get("updated"))
    if reviewed is not None and updated is not None and reviewed < updated:
        return [Diagnostic(note.path, "stale-review", "reviewed is older than updated (stale review)")]
    return []


def _check_index(note: TxNote) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    title = note.data.metadata.get("title")
    if _present(title) and not str(title).startswith(_INDEX_TITLE_PREFIX):
        found.append(Diagnostic(note.path, "index-title", f"index title must start with '§ ', got {str(title)!r}"))
    opens = note.body.count(MEMBERS_OPEN)
    closes = note.body.count(MEMBERS_CLOSE)
    ordered = opens == closes == 1 and note.body.index(MEMBERS_OPEN) < note.body.index(MEMBERS_CLOSE)
    if (opens, closes) != (0, 0) and not ordered:
        message = f"members block needs one {MEMBERS_OPEN} before one {MEMBERS_CLOSE}, or neither"
        found.append(Diagnostic(note.path, "members-block", message))
    return found


def _check_concept_fields(note: TxNote) -> list[Diagnostic]:
    meta = note.data.metadata
    found: list[Diagnostic] = []
    note_type = meta.get("type")
    if _present(note_type) and note_type not in CONCEPT_NOTE_TYPES:
        found.append(Diagnostic(note.path, "type-species", f"type {note_type!r} is not a concept note type"))
    enums = (
        ("concept-type", CONCEPT_TYPE_VALUES, "concept-type-enum"),
        ("assent", ASSENT_VALUES, "assent-enum"),
        ("lifecycle", LIFECYCLE_VALUES, "lifecycle-enum"),
    )
    for field, allowed, rule in enums:
        value = meta.get(field)
        if (field == "concept-type" or value is not None) and not _in(value, allowed):
            found.append(Diagnostic(note.path, rule, f"{field} {value!r} is not one of {sorted(allowed)}"))
    if not parents(note.data):
        found.append(Diagnostic(note.path, "orphan-concept", "concept note has no parent link (orphan)"))
    return found


def _check_claims(note: TxNote) -> list[Diagnostic]:
    claims = note.data.metadata.get("claims")
    concept_type = note.data.metadata.get("concept-type")
    bearing = _in(concept_type, CLAIM_BEARING_CONCEPT_TYPES)
    aporia = concept_type == ConceptType.APORIA.value
    found: list[Diagnostic] = []
    if claims is not None and not isinstance(claims, list):
        found.append(Diagnostic(note.path, "claims-shape", "claims must be a list"))
    if isinstance(claims, list):
        for number, claim in enumerate(claims, 1):
            if not isinstance(claim, dict) or "id" not in claim or "statement" not in claim:
                found.append(Diagnostic(note.path, "claim-shape", f"claim #{number} must have 'id' and 'statement'"))
        if len(claims) > _MAX_CLAIMS or (not claims and not bearing and not aporia):
            found.append(Diagnostic(note.path, "claims-count", f"claims holds {len(claims)} entries, allowed 1 to 3"))
    if bearing and (claims is None or claims == []):
        message = f"concept-type {concept_type!r} requires a non-empty claims list"
        found.append(Diagnostic(note.path, "claims-required", message))
    if aporia and isinstance(claims, list) and claims:
        found.append(Diagnostic(note.path, "aporia-no-claims", "aporia notes carry no claims of their own"))
    return found


def _check_doubts(note: TxNote) -> list[Diagnostic]:
    doubts = note.data.metadata.get("doubts")
    if doubts is None:
        return []
    if not isinstance(doubts, list):
        return [Diagnostic(note.path, "doubts-shape", "doubts must be a list")]
    found: list[Diagnostic] = []
    for number, doubt in enumerate(doubts, 1):
        if not isinstance(doubt, dict):
            found.append(Diagnostic(note.path, "doubt-shape", f"doubt #{number} must be a mapping"))
            continue
        if not {"mode", "claim", "rationale"} <= doubt.keys():
            message = f"doubt #{number} must have 'mode', 'claim' and 'rationale'"
            found.append(Diagnostic(note.path, "doubt-shape", message))
        mode = doubt.get("mode")
        if mode is not None and not _in(mode, DOUBT_MODE_VALUES):
            message = f"doubt mode {mode!r} is not one of {sorted(DOUBT_MODE_VALUES)}"
            found.append(Diagnostic(note.path, "doubt-mode-enum", message))
        target = doubt.get("target")
        bad_target = not isinstance(target, dict) or not {"to", "claim"} <= target.keys()
        if mode == DoubtMode.DISAGREEMENT.value and "target" in doubt and bad_target:
            message = f"doubt #{number} target must have 'to' and 'claim'"
            found.append(Diagnostic(note.path, "doubt-target-shape", message))
    return found


def _check_sources(note: TxNote) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for value in sources(note.data):
        _, separator, rest = value.removeprefix(MIRROR_PREFIX).partition("/")
        rel = PurePosixPath(rest)
        if not value.startswith(MIRROR_PREFIX) or not separator or rel.is_absolute() or ".." in rel.parts:
            message = f"source {value!r} must be mirror:<root>/<relative path> without '..'"
            found.append(Diagnostic(note.path, "source-shape", message))
    return found


def validate_note(note: TxNote, *, max_body_lines: int = 60) -> list[Diagnostic]:
    """Run every rule that needs only this one note.

    Args:
        note: The parsed note.
        max_body_lines: The most non-blank body lines a concept or index note may hold.

    Returns:
        The diagnostics of the note; plain notes get only ``required-field``.
    """
    found = _check_required(note)
    if note.kind is NoteKind.PLAIN:
        return found
    found += _check_publish_and_tags(note) + _check_h1(note) + _check_id(note)
    if note.kind is NoteKind.RUN:
        return found
    found += _check_body(note, max_body_lines) + _check_links(note) + _check_review(note)
    if note.kind is NoteKind.INDEX:
        return found + _check_index(note)
    return found + _check_concept_fields(note) + _check_claims(note) + _check_doubts(note) + _check_sources(note)


def _check_target(paths: TiromexPaths, note: TxNote, vault_rel: str, rule: str | None) -> list[Diagnostic]:
    """Give ``path-confinement`` when the target leaves the folder, else ``rule`` when it is no file."""
    try:
        file = confine(paths, vault_rel)
    except ValueError as exc:
        return [Diagnostic(note.path, "path-confinement", str(exc))]
    if rule is None or file.is_file():
        return []
    return [Diagnostic(note.path, rule, f"target {vault_rel!r} is not an existing note file")]


def _check_references(paths: TiromexPaths, note: TxNote) -> list[Diagnostic]:
    if note.kind not in (NoteKind.CONCEPT, NoteKind.INDEX):
        return []
    concept = note.kind is NoteKind.CONCEPT
    found: list[Diagnostic] = []
    for _, link in relations(note.data):
        found += _check_target(paths, note, link_file(link.target), "dangling-link" if concept else None)
    for link in parents(note.data):
        found += _check_target(paths, note, link_file(link.target), "dangling-moc")
    if not concept or not isinstance(note.data.metadata.get("doubts"), list):
        return found
    for doubt in note.data.metadata["doubts"]:
        target = doubt.get("target") if isinstance(doubt, dict) else None
        to = target.get("to") if isinstance(target, dict) else None
        if not isinstance(to, str):
            continue
        checked = _check_target(paths, note, to, "dangling-doubt-target")
        if not checked and not to.endswith(".md"):
            checked = [Diagnostic(note.path, "dangling-doubt-target", f"doubt target {to!r} must end with .md")]
        found += checked
    return found


def _first_cycle(adjacency: dict[str, list[str]]) -> list[str] | None:
    """Return the first cycle found via DFS, or None. States: 0 unseen, 1 active, 2 done."""
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in adjacency.get(node, []):
            if nxt not in adjacency:
                continue
            if state.get(nxt, 0) == 1:
                return [*stack[stack.index(nxt) :], nxt]
            if state.get(nxt, 0) == 0:
                found = visit(nxt)
                if found is not None:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in adjacency:
        if state.get(node, 0) == 0:
            found = visit(node)
            if found is not None:
                return found
    return None


def _edges(paths: TiromexPaths, note: TxNote, relation: str, keys: set[str]) -> list[str]:
    edges: list[str] = []
    for link in parse_links(note.data.reference.get(relation)):
        try:
            target = to_vault_rel(paths, confine(paths, link_file(link.target)))
        except ValueError:
            continue
        if target in keys:
            edges.append(target)
    return edges


def _check_cycles(paths: TiromexPaths, concepts: list[TxNote]) -> list[Diagnostic]:
    keys = {note.path for note in concepts}
    found: list[Diagnostic] = []
    for relation in TRANSITIVE_RELATIONS:
        cycle = _first_cycle({note.path: _edges(paths, note, relation, keys) for note in concepts})
        if cycle is not None:
            message = f"cycle in transitive relation {relation!r}: {' -> '.join(cycle)}"
            found.append(Diagnostic(cycle[0], "transitive-cycle", message))
    return found


def validate_tiromex(paths: TiromexPaths, *, max_body_lines: int = 60) -> list[Diagnostic]:
    """Validate every note file in the tiromex folder.

    Args:
        paths: The resolved tiromex paths.
        max_body_lines: The most non-blank body lines a concept or index note may hold.

    Returns:
        The per-note diagnostics of each file in path order, then the graph
        diagnostics. A file that cannot be read or parsed gives one
        ``parse-error`` and is left out of the graph.
    """
    found: list[Diagnostic] = []
    notes: list[TxNote] = []
    for file in iter_note_files(paths):
        try:
            note = read_note(paths, file)
        except (OSError, ValueError) as exc:
            found.append(Diagnostic(to_vault_rel(paths, file), "parse-error", f"cannot read or parse the note: {exc}"))
            continue
        notes.append(note)
        found += validate_note(note, max_body_lines=max_body_lines)
    for note in notes:
        found += _check_references(paths, note)
    return found + _check_cycles(paths, [note for note in notes if note.kind is NoteKind.CONCEPT])
