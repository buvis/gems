"""Resolve every detected conflict into exactly one structure (spec 8).

None coexists silently. A conflict from the payload becomes links and doubts on
the new zettel plus the minimum edit on the existing one:

- **aporia**: ``contradicts`` on BOTH sides (the symmetric relation materialised
  both ways) plus a ``disagreement`` doubt with a ``target`` on both sides, so
  the reciprocity spec 7.6 derives aporia from actually exists. A claim-less
  ``concept-type: aporia`` zettel the backend also returned is already rendered;
  this module does not re-create it.
- **refine**: ``narrower-than`` from the new zettel to the target only; the
  ``broader-than`` inverse is derived at query time, never stored (spec 8).
- **supersede**: ``supersedes`` from the new zettel to the target, and the
  target moves to ``assent: rejected``.

Editing an existing zettel's doubts is a content change: it resets
``processed: false`` and bumps ``updated`` (spec 7.7). The supersede loser's
assent-only change does neither. A conflict whose target already carries
``assent: rejected`` is dropped before any edit and logged as corroborating the
existing rejection (discovery Q13), whatever the backend proposed.

Corroboration (``supports``) is recorded on the new zettel only; the
corroborated zettel is not edited (PRD "Corroboration recording").
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from klyreon.backends.base import ConflictEntry, ConflictShape, IngestPayload
from klyreon.ingest.render import RenderedZettel
from klyreon.spec.enums import Assent, DoubtMode, Relation
from klyreon.spec.model import Document, FileKind
from klyreon.spec.parser import parse_file

__all__ = ["ConflictOutcome", "EditedZettel", "apply_conflicts", "apply_corroborations"]


@dataclass(frozen=True, slots=True)
class EditedZettel:
    """An existing zettel changed by conflict resolution, ready to stage."""

    rel_path: str
    document: Document


@dataclass(slots=True)
class ConflictOutcome:
    """What conflict resolution produced for one source.

    ``edits`` are existing zettels to stage; the new zettels are mutated in
    place inside ``rendered``. ``trail_lines`` records each conflict and the
    shape it resolved into (or the rejected-target drop).
    """

    edits: list[EditedZettel] = field(default_factory=list)
    trail_lines: list[str] = field(default_factory=list)


def _add_link(doc: Document, rel: str, to: str) -> None:
    links = cast("list[dict[str, object]]", doc.frontmatter.setdefault("links", []))
    if not any(entry.get("rel") == rel and entry.get("to") == to for entry in links):
        links.append({"rel": rel, "to": to})


def _add_doubt(doc: Document, *, claim: str | None, target_to: str, target_claim: str | None, rationale: str) -> None:
    doubts = cast("list[dict[str, object]]", doc.frontmatter.setdefault("doubts", []))
    doubts.append(
        {
            "mode": DoubtMode.DISAGREEMENT.value,
            "claim": claim,
            "rationale": rationale,
            "target": {"to": target_to, "claim": target_claim},
        },
    )


def _touch_content(doc: Document, now: dt.datetime) -> None:
    """A content change: reset processed and bump updated (spec 7.7).

    A prior human ``reviewed`` timestamp no longer attests to the changed
    content, so it is dropped: leaving it would be older than ``updated`` and
    the validator (correctly) reports that as a stale review. Dropping it keeps
    the vault ``validate``-clean while still signalling ``processed: false``.
    """
    doc.frontmatter["processed"] = False
    doc.frontmatter["updated"] = now.isoformat()
    doc.frontmatter.pop("reviewed", None)


def _load_existing(root: Path, rel_path: str, cache: dict[str, Document]) -> Document:
    if rel_path not in cache:
        doc = parse_file(root / rel_path, FileKind.ZETTEL)
        cache[rel_path] = Document(
            path=rel_path,
            kind=FileKind.ZETTEL,
            frontmatter=doc.frontmatter,
            body=doc.body,
            h1=doc.h1,
        )
    return cache[rel_path]


def apply_conflicts(
    payload: IngestPayload,
    rendered: list[RenderedZettel],
    *,
    root: Path,
    now: dt.datetime,
) -> ConflictOutcome:
    """Resolve every conflict in ``payload`` into its one structure.

    Mutates the matching new zettels inside ``rendered`` in place and returns
    the existing-zettel edits plus the trail lines.
    """
    outcome = ConflictOutcome()
    edit_cache: dict[str, Document] = {}
    edited_paths: set[str] = set()

    for conflict in payload.conflicts:
        new = rendered[conflict.new_zettel]
        new_path = new.rel_path
        target_path = conflict.target.to

        existing = _load_existing(root, target_path, edit_cache)
        if existing.get("assent") == Assent.REJECTED.value:
            # Rejected-target drop (discovery Q13): no edit, one trail line.
            outcome.trail_lines.append(
                f"conflict {new_path}#{conflict.new_claim or '?'} -> {target_path}: "
                "target already rejected; dropped, corroborates the existing rejection",
            )
            continue

        edited = _resolve_one(conflict, new=new, existing=existing, outcome=outcome, now=now)
        if edited:
            edited_paths.add(target_path)

    outcome.edits = [EditedZettel(rel_path=rel, document=doc) for rel, doc in edit_cache.items() if rel in edited_paths]
    return outcome


def _resolve_one(
    conflict: ConflictEntry,
    *,
    new: RenderedZettel,
    existing: Document,
    outcome: ConflictOutcome,
    now: dt.datetime,
) -> bool:
    """Resolve one conflict. Returns True when the existing zettel was edited."""
    target_path = conflict.target.to
    target_claim = conflict.target.claim
    new_doc = new.document
    new_path = new.rel_path

    if conflict.shape is ConflictShape.APORIA:
        # Symmetric contradicts on both sides.
        _add_link(new_doc, Relation.CONTRADICTS.value, target_path)
        _add_link(existing, Relation.CONTRADICTS.value, new_path)
        # Disagreement doubt with target on both sides.
        _add_doubt(
            new_doc,
            claim=conflict.new_claim,
            target_to=target_path,
            target_claim=target_claim,
            rationale=conflict.rationale or "aporia: both sides defensible",
        )
        _add_doubt(
            existing,
            claim=target_claim,
            target_to=new_path,
            target_claim=conflict.new_claim,
            rationale=conflict.rationale or "aporia: both sides defensible",
        )
        _touch_content(existing, now)  # editing existing doubts is a content change
        outcome.trail_lines.append(f"conflict {new_path} vs {target_path}: resolved as APORIA")
        return True

    if conflict.shape is ConflictShape.REFINE:
        # narrower-than from new to target only; inverse derived at query time.
        # The target is NOT edited.
        _add_link(new_doc, Relation.NARROWER_THAN.value, target_path)
        outcome.trail_lines.append(f"conflict {new_path} vs {target_path}: resolved as REFINE (narrower-than)")
        return False

    # SUPERSEDE
    _add_link(new_doc, Relation.SUPERSEDES.value, target_path)
    # Loser moves to rejected: assent-only change, no processed reset / no updated bump.
    existing.frontmatter["assent"] = Assent.REJECTED.value
    outcome.trail_lines.append(f"conflict {new_path} vs {target_path}: resolved as SUPERSEDE (target rejected)")
    return True


def apply_corroborations(
    payload: IngestPayload,
    rendered: list[RenderedZettel],
) -> list[str]:
    """Add a ``supports`` link from each corroborating new zettel to its target.

    The corroborated zettel is not edited (PRD "Corroboration recording").
    Returns the trail lines.
    """
    lines: list[str] = []
    for corro in payload.corroborations:
        new_doc = rendered[corro.new_zettel].document
        new_path = rendered[corro.new_zettel].rel_path
        _add_link(new_doc, Relation.SUPPORTS.value, corro.target.to)
        lines.append(f"corroboration {new_path} -> {corro.target.to}: supports")
    return lines
