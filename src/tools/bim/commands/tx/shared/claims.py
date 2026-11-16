"""Collect the claim rows of tiromex concept notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .format import Assent, Lifecycle, NoteKind

if TYPE_CHECKING:
    from .format import TxNote


def _filled(claim: dict[object, object], key: str) -> bool:
    value = claim.get(key)
    return value is not None and bool(str(value).strip())


def collect_claims(notes: list[TxNote]) -> list[dict[str, object]]:
    """Return one row per well-formed claim on a concept note.

    A claim is well-formed when it is a mapping whose ``id`` and ``statement``
    are present, not ``None`` and not blank. Rejected notes are included; other
    note kinds contribute nothing.

    Args:
        notes: The parsed notes, in any order.

    Returns:
        Rows in note-path order then claim order, with the keys ``zettel``,
        ``assent``, ``lifecycle``, ``claim_id`` and ``statement``, every value a string.
    """
    rows: list[dict[str, object]] = []
    for note in sorted(notes, key=lambda note: note.path):
        if note.kind is not NoteKind.CONCEPT:
            continue
        meta = note.data.metadata
        claims = meta.get("claims")
        if not isinstance(claims, list):
            continue
        assent = str(meta.get("assent", Assent.UNKNOWN.value))
        lifecycle = str(meta.get("lifecycle", Lifecycle.FLEETING.value))
        rows.extend(
            {
                "zettel": note.path,
                "assent": assent,
                "lifecycle": lifecycle,
                "claim_id": str(claim["id"]),
                "statement": str(claim["statement"]),
            }
            for claim in claims
            if isinstance(claim, dict) and _filled(claim, "id") and _filled(claim, "statement")
        )
    return rows
