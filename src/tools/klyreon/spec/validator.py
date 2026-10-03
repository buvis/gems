"""File-level and vault-level validation against the format spec.

Pure: no console, no Click, no git. Every check returns :class:`SpecError`
objects carrying the path, a stable ``rule`` id, a message, and the line when
derivable. ``validate_file`` needs only the one file; ``validate_vault`` adds
the checks that need the whole graph (reference resolution, the transitive
cycle check, orphan/oversized/stale lint).

Rule ids are stable strings so a test can assert that one invalid fixture
produces exactly its own rule and no other.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from klyreon.spec.enums import (
    CLAIM_BEARING_CONCEPT_TYPES,
    TRANSITIVE_RELATIONS,
    Assent,
    AuxKind,
    ConceptType,
    DoubtMode,
    Lifecycle,
    Relation,
    SourceType,
    ZettelType,
)
from klyreon.spec.model import Document, FileKind
from klyreon.spec.parser import FrontmatterError, parse_file
from klyreon.vault.paths import PathConfinementError, resolve_path

__all__ = ["SpecError", "validate_file", "validate_vault"]

_ZETTEL_ID_RE = re.compile(r"^\d{14}$")
_SOURCE_TYPES = {t.value for t in SourceType}
_ZETTEL_TYPES = {t.value for t in ZettelType}
_CONCEPT_TYPES = {t.value for t in ConceptType}
_ASSENT = {t.value for t in Assent}
_LIFECYCLE = {t.value for t in Lifecycle}
_DOUBT_MODES = {t.value for t in DoubtMode}
_RELATIONS = {t.value for t in Relation}
_AUX_KINDS = {t.value for t in AuxKind}
_CONCEPT_ONLY_FIELDS = ("concept-type", "assent", "lifecycle", "claims", "doubts")


@dataclass(frozen=True, slots=True)
class SpecError:
    """One validation failure.

    Attributes:
        path: The file the error is about (as given to the validator).
        rule: A stable rule id, e.g. ``required-field`` or ``id-filename-mismatch``.
        message: A human-readable, located explanation.
        line: The 1-based line where derivable, else ``None``.
    """

    path: str
    rule: str
    message: str
    line: int | None = None


# --------------------------------------------------------------------------- #
# File-level validation
# --------------------------------------------------------------------------- #


def _require_fields(doc: Document, required: tuple[str, ...]) -> list[SpecError]:
    errors: list[SpecError] = []
    for name in required:
        value = doc.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(
                SpecError(doc.path, "required-field", f"missing required field {name!r}"),
            )
    return errors


def _check_h1(doc: Document) -> list[SpecError]:
    errors: list[SpecError] = []
    h1_count = len(re.findall(r"^#[ \t]+\S", doc.body, re.MULTILINE))
    if h1_count != 1:
        errors.append(
            SpecError(doc.path, "h1-exactly-one", f"body must have exactly one H1, found {h1_count}"),
        )
    title = doc.get("title")
    if doc.h1 is not None and isinstance(title, str) and doc.h1 != title:
        errors.append(
            SpecError(
                doc.path,
                "h1-title-mismatch",
                f"H1 {doc.h1!r} does not equal title {title!r}",
            ),
        )
    return errors


def _check_id_matches_stem(doc: Document) -> list[SpecError]:
    stem = PurePosixPath(doc.path).stem
    file_id = doc.get("id")
    if isinstance(file_id, str) and file_id != stem:
        return [
            SpecError(
                doc.path,
                "id-filename-mismatch",
                f"id {file_id!r} must equal the filename stem {stem!r}",
            ),
        ]
    return []


def _parse_iso(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _check_zettel_id_and_created(doc: Document) -> list[SpecError]:
    """14-digit id and `created` agreeing to the second (zettels and trails)."""
    errors: list[SpecError] = []
    file_id = doc.get("id")
    if not isinstance(file_id, str) or not _ZETTEL_ID_RE.match(file_id):
        errors.append(
            SpecError(doc.path, "zettel-id-format", f"zettel id must be exactly 14 digits, got {file_id!r}"),
        )
        return errors
    created = _parse_iso(doc.get("created"))
    if created is not None:
        expected = created.strftime("%Y%m%d%H%M%S")
        if expected != file_id:
            errors.append(
                SpecError(
                    doc.path,
                    "id-created-mismatch",
                    f"created {doc.get('created')!r} does not agree with id {file_id!r} to the second",
                ),
            )
    return errors


def _check_enum(doc: Document, field: str, allowed: set[str], rule: str) -> list[SpecError]:
    value = doc.get(field)
    if value is not None and value not in allowed:
        return [
            SpecError(
                doc.path,
                rule,
                f"{field} {value!r} is not one of {sorted(allowed)}",
            ),
        ]
    return []


def _check_claims(doc: Document) -> list[SpecError]:
    errors: list[SpecError] = []
    claims = doc.get("claims")
    concept_type = doc.get("concept-type")

    if claims is not None:
        if not isinstance(claims, list):
            errors.append(SpecError(doc.path, "claims-shape", "claims must be a list"))
        else:
            for idx, claim in enumerate(claims):
                if not isinstance(claim, dict) or "id" not in claim or "statement" not in claim:
                    errors.append(
                        SpecError(
                            doc.path,
                            "claim-shape",
                            f"claim #{idx + 1} must have 'id' and 'statement'",
                        ),
                    )

    if concept_type in CLAIM_BEARING_CONCEPT_TYPES:
        if not claims:
            errors.append(
                SpecError(
                    doc.path,
                    "claims-required",
                    f"concept-type {concept_type!r} requires a non-empty 'claims' list",
                ),
            )
    elif concept_type == ConceptType.APORIA.value and claims:
        errors.append(
            SpecError(doc.path, "aporia-no-claims", "aporia zettels carry no claims of their own"),
        )
    return errors


def _check_doubts(doc: Document) -> list[SpecError]:
    errors: list[SpecError] = []
    doubts = doc.get("doubts")
    if doubts is None:
        return errors
    if not isinstance(doubts, list):
        return [SpecError(doc.path, "doubts-shape", "doubts must be a list")]

    for idx, doubt in enumerate(doubts):
        if not isinstance(doubt, dict):
            errors.append(SpecError(doc.path, "doubt-shape", f"doubt #{idx + 1} must be a mapping"))
            continue
        if "mode" not in doubt or "claim" not in doubt or "rationale" not in doubt:
            errors.append(
                SpecError(
                    doc.path,
                    "doubt-shape",
                    f"doubt #{idx + 1} must have 'mode', 'claim' and 'rationale'",
                ),
            )
        mode = doubt.get("mode")
        if mode is not None and mode not in _DOUBT_MODES:
            errors.append(
                SpecError(doc.path, "doubt-mode-enum", f"doubt mode {mode!r} is not one of {sorted(_DOUBT_MODES)}"),
            )
        if mode == DoubtMode.DISAGREEMENT.value and "target" in doubt:
            target = doubt.get("target")
            if not isinstance(target, dict) or "to" not in target or "claim" not in target:
                errors.append(
                    SpecError(
                        doc.path,
                        "doubt-target-shape",
                        f"doubt #{idx + 1} target must have 'to' and 'claim'",
                    ),
                )
    return errors


def _check_links(doc: Document) -> list[SpecError]:
    errors: list[SpecError] = []
    links = doc.get("links")
    if links is None:
        return errors
    if not isinstance(links, list):
        return [SpecError(doc.path, "links-shape", "links must be a list")]
    for idx, link in enumerate(links):
        if not isinstance(link, dict) or "rel" not in link or "to" not in link:
            errors.append(
                SpecError(doc.path, "link-shape", f"link #{idx + 1} must have 'rel' and 'to'"),
            )
            continue
        rel = link.get("rel")
        if rel not in _RELATIONS:
            errors.append(
                SpecError(doc.path, "link-rel-enum", f"link rel {rel!r} is not one of {sorted(_RELATIONS)}"),
            )
    return errors


def _check_species_fields(doc: Document) -> list[SpecError]:
    """type/species coherence, and concept-only fields absent on source docs."""
    errors: list[SpecError] = []
    file_type = doc.get("type")

    if doc.kind is FileKind.SOURCE:
        if file_type is not None and file_type not in _SOURCE_TYPES:
            errors.append(
                SpecError(doc.path, "type-species", f"source-document type {file_type!r} invalid or is a zettel type"),
            )
        for field in _CONCEPT_ONLY_FIELDS:
            if doc.get(field) is not None:
                errors.append(
                    SpecError(
                        doc.path,
                        "concept-field-on-source",
                        f"{field!r} must not appear on a source document",
                    ),
                )
    elif doc.kind is FileKind.ZETTEL and file_type is not None and file_type not in _ZETTEL_TYPES:
        errors.append(
            SpecError(doc.path, "type-species", f"zettel type {file_type!r} invalid or is a source-document type"),
        )
    return errors


def _check_publish(doc: Document) -> list[SpecError]:
    if doc.get("publish") is True:
        return [SpecError(doc.path, "publish-true", "publish must never be true when written by a tool")]
    return []


def validate_file(doc: Document, path: str | None = None) -> list[SpecError]:
    """Run every check that needs only this one file.

    ``path`` overrides ``doc.path`` for the error reports when given.
    """
    if path is not None:
        doc = Document(path=path, kind=doc.kind, frontmatter=doc.frontmatter, body=doc.body, h1=doc.h1)

    errors: list[SpecError] = []
    if doc.kind is FileKind.AUX:
        errors += _require_fields(doc, ("id", "title", "created", "kind"))
        errors += _check_enum(doc, "kind", _AUX_KINDS, "aux-kind-enum")
    else:
        errors += _require_fields(doc, ("id", "title", "created", "type"))

    errors += _check_id_matches_stem(doc)
    errors += _check_h1(doc)

    if doc.kind in (FileKind.ZETTEL, FileKind.AUX):
        # Trails and zettels share the 14-digit id/created rule; MOCs use a
        # kebab slug id, so only apply it when the id looks timestamp-shaped.
        file_id = doc.get("id")
        is_slug_moc = doc.kind is FileKind.AUX and doc.get("kind") == AuxKind.MOC.value
        if not is_slug_moc or (isinstance(file_id, str) and _ZETTEL_ID_RE.match(file_id)):
            if doc.kind is FileKind.ZETTEL:
                errors += _check_zettel_id_and_created(doc)

    errors += _check_species_fields(doc)
    if doc.kind is FileKind.ZETTEL:
        errors += _check_enum(doc, "concept-type", _CONCEPT_TYPES, "concept-type-enum")
        errors += _check_enum(doc, "assent", _ASSENT, "assent-enum")
        errors += _check_enum(doc, "lifecycle", _LIFECYCLE, "lifecycle-enum")
        errors += _check_claims(doc)
        errors += _check_doubts(doc)
        errors += _check_links(doc)
    errors += _check_publish(doc)
    return errors


# --------------------------------------------------------------------------- #
# Vault-level validation
# --------------------------------------------------------------------------- #


def _kind_for(rel_path: str) -> FileKind | None:
    parts = PurePosixPath(rel_path).parts
    if parts[:1] == ("sources",):
        return FileKind.SOURCE
    if parts[:2] == ("wiki", "notes"):
        return FileKind.ZETTEL
    if parts[:2] == ("wiki", "mocs") or parts[:2] == ("wiki", "trails"):
        return FileKind.AUX
    return None


def _iter_vault_files(root: Path) -> list[tuple[str, FileKind]]:
    found: list[tuple[str, FileKind]] = []
    for sub, kind in (
        ("sources", FileKind.SOURCE),
        ("wiki/notes", FileKind.ZETTEL),
        ("wiki/mocs", FileKind.AUX),
        ("wiki/trails", FileKind.AUX),
    ):
        base = root / sub
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            found.append((md.relative_to(root).as_posix(), kind))
    return found


def _ref_exists(root: Path, rel: str) -> bool:
    try:
        resolved = resolve_path(root, rel)
    except PathConfinementError:
        return False
    return resolved.exists()


def _check_reference(
    root: Path,
    doc_path: str,
    rel: str,
    rule: str,
) -> list[SpecError]:
    try:
        resolve_path(root, rel)
    except PathConfinementError as exc:
        return [SpecError(doc_path, "path-confinement", str(exc))]
    if not (root / rel).exists():
        return [SpecError(doc_path, rule, f"referenced path does not resolve to an existing file: {rel!r}")]
    return []


def _collect_graph_errors(  # noqa: PLR0912 - one pass over all reference kinds
    root: Path,
    doc: Document,
    max_body_lines: int,
) -> list[SpecError]:
    errors: list[SpecError] = []
    path = doc.path

    for rel in doc.get("sources") or []:
        if isinstance(rel, str):
            errors += _check_reference(root, path, rel, "dangling-source")

    for rel in doc.get("mocs") or []:
        if isinstance(rel, str):
            errors += _check_reference(root, path, rel, "dangling-moc")

    for link in doc.get("links") or []:
        if isinstance(link, dict) and isinstance(link.get("to"), str):
            to = link["to"]
            errors += _check_reference(root, path, to, "dangling-link")
            if _kind_for(to) is FileKind.SOURCE:
                errors.append(
                    SpecError(path, "link-to-source", f"links.to must target a zettel, not a source document: {to!r}"),
                )

    for doubt in doc.get("doubts") or []:
        if isinstance(doubt, dict) and isinstance(doubt.get("target"), dict):
            to = doubt["target"].get("to")
            if isinstance(to, str):
                errors += _check_reference(root, path, to, "dangling-doubt-target")

    for tag in doc.get("tags") or []:
        if isinstance(tag, str) and ":" in tag:
            errors.append(SpecError(path, "legacy-colon-tag", f"colon-prefixed legacy tag flagged: {tag!r}"))

    if doc.kind is FileKind.ZETTEL and doc.get("concept-type") is not None and not (doc.get("mocs")):
        errors.append(SpecError(path, "orphan-concept", "concept zettel links into no MOC (orphan)"))

    body_lines = len([ln for ln in doc.body.strip().splitlines() if ln.strip()])
    if body_lines > max_body_lines:
        errors.append(
            SpecError(path, "oversized-body", f"body has {body_lines} non-blank lines, exceeds max {max_body_lines}"),
        )

    updated = _parse_iso(doc.get("updated"))
    reviewed = _parse_iso(doc.get("reviewed"))
    if updated is not None and reviewed is not None and reviewed < updated:
        errors.append(SpecError(path, "stale-review", "reviewed is older than updated (stale review)"))

    return errors


def _check_transitive_cycles(docs: dict[str, Document]) -> list[SpecError]:
    """Detect a cycle in any transitive relation (requires/broader/narrower)."""
    errors: list[SpecError] = []
    for relation in TRANSITIVE_RELATIONS:
        adjacency: dict[str, list[str]] = {}
        for src, doc in docs.items():
            targets: list[str] = []
            for link in doc.get("links") or []:
                if isinstance(link, dict) and link.get("rel") == relation and isinstance(link.get("to"), str):
                    targets.append(link["to"])
            adjacency[src] = targets

        cycle = _first_cycle(adjacency)
        if cycle is not None:
            errors.append(
                SpecError(
                    cycle[0],
                    "transitive-cycle",
                    f"cycle in transitive relation {relation!r}: {' -> '.join(cycle)}",
                ),
            )
    return errors


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
                idx = stack.index(nxt)
                return [*stack[idx:], nxt]
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


def validate_vault(root: Path, max_body_lines: int = 60) -> list[SpecError]:
    """Run every mechanical check over the whole vault at ``root``.

    Returns file-level errors for every file plus graph-level errors.
    """
    errors: list[SpecError] = []
    docs: dict[str, Document] = {}

    for rel_path, kind in _iter_vault_files(root):
        try:
            doc = parse_file(root / rel_path, kind)
        except (FrontmatterError, OSError) as exc:
            errors.append(SpecError(rel_path, "parse-error", str(exc)))
            continue
        doc = Document(path=rel_path, kind=kind, frontmatter=doc.frontmatter, body=doc.body, h1=doc.h1)
        docs[rel_path] = doc
        errors += validate_file(doc)
        errors += _collect_graph_errors(root, doc, max_body_lines)

    errors += _check_transitive_cycles(docs)
    return errors
