"""Phase 1: conflict resolution into the three shapes + corroboration."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from klyreon.backends.base import (
    ConflictEntry,
    ConflictShape,
    CorroborationEntry,
    IngestPayload,
    LinkTarget,
    PayloadClaim,
    ZettelDraft,
)
from klyreon.ingest.conflicts import apply_conflicts, apply_corroborations
from klyreon.ingest.render import render_zettels

pytestmark = pytest.mark.klyreon

NOW = dt.datetime(2026, 5, 2, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
ARCHIVE = "sources/archive/2026-05/x.md"
ACCEPTED = "wiki/notes/20260301090000.md"
REJECTED = "wiki/notes/20260301093000.md"


def _render_one(conflict_vault: Path, concept_type: str = "thesis") -> list:
    payload = IngestPayload(
        zettels=[
            ZettelDraft(
                title="New claim",
                concept_type=concept_type,
                claims=[PayloadClaim(id="c1", statement="a new claim")] if concept_type != "aporia" else [],
                mocs=["wiki/mocs/epistemics.md"],
            ),
        ],
    )
    return render_zettels(payload, source_archive_path=ARCHIVE, notes_dir=conflict_vault / "wiki" / "notes", now=NOW)


def _links(doc, rel: str) -> list[str]:
    return [e["to"] for e in (doc.get("links") or []) if e.get("rel") == rel]


def _disagreement_targets(doc) -> list[str]:
    return [d["target"]["to"] for d in (doc.get("doubts") or []) if d.get("mode") == "disagreement"]


class TestAporia:
    def test_contradicts_and_doubts_on_both_sides(self, conflict_vault: Path) -> None:
        rendered = _render_one(conflict_vault)
        payload = IngestPayload()
        payload.conflicts = [
            ConflictEntry(
                new_zettel=0, new_claim="c1", target=LinkTarget(to=ACCEPTED, claim="c1"), shape=ConflictShape.APORIA
            ),
        ]
        outcome = apply_conflicts(payload, rendered, root=conflict_vault, now=NOW)

        new_doc = rendered[0].document
        new_path = rendered[0].rel_path
        # Both sides carry contradicts.
        assert _links(new_doc, "contradicts") == [ACCEPTED]
        edited = {e.rel_path: e.document for e in outcome.edits}
        assert ACCEPTED in edited
        assert _links(edited[ACCEPTED], "contradicts") == [new_path]
        # Disagreement doubt with target on both sides.
        assert _disagreement_targets(new_doc) == [ACCEPTED]
        assert _disagreement_targets(edited[ACCEPTED]) == [new_path]
        # Editing existing doubts is a content change: processed reset + updated bumped.
        assert edited[ACCEPTED].get("processed") is False
        assert edited[ACCEPTED].get("updated") == NOW.isoformat()
        assert any("APORIA" in line for line in outcome.trail_lines)


class TestRefine:
    def test_narrower_than_new_to_target_only(self, conflict_vault: Path) -> None:
        rendered = _render_one(conflict_vault)
        payload = IngestPayload()
        payload.conflicts = [
            ConflictEntry(
                new_zettel=0, new_claim="c1", target=LinkTarget(to=ACCEPTED, claim="c1"), shape=ConflictShape.REFINE
            ),
        ]
        outcome = apply_conflicts(payload, rendered, root=conflict_vault, now=NOW)
        assert _links(rendered[0].document, "narrower-than") == [ACCEPTED]
        # No inverse stored, and the target is not edited.
        assert not outcome.edits
        assert any("REFINE" in line for line in outcome.trail_lines)


class TestSupersede:
    def test_supersedes_and_target_rejected_without_processed_reset(self, conflict_vault: Path) -> None:
        rendered = _render_one(conflict_vault)
        payload = IngestPayload()
        payload.conflicts = [
            ConflictEntry(
                new_zettel=0, new_claim="c1", target=LinkTarget(to=ACCEPTED, claim="c1"), shape=ConflictShape.SUPERSEDE
            ),
        ]
        outcome = apply_conflicts(payload, rendered, root=conflict_vault, now=NOW)
        assert _links(rendered[0].document, "supersedes") == [ACCEPTED]
        edited = {e.rel_path: e.document for e in outcome.edits}
        assert edited[ACCEPTED].get("assent") == "rejected"
        # Assent-only change: processed stays true (as in the fixture), no updated bump.
        assert edited[ACCEPTED].get("processed") is True
        assert "updated" not in edited[ACCEPTED].frontmatter
        assert any("SUPERSEDE" in line for line in outcome.trail_lines)


class TestRejectedTargetDrop:
    def test_no_edit_and_one_trail_line(self, conflict_vault: Path) -> None:
        rendered = _render_one(conflict_vault)
        payload = IngestPayload()
        payload.conflicts = [
            ConflictEntry(
                new_zettel=0, new_claim="c1", target=LinkTarget(to=REJECTED, claim="c1"), shape=ConflictShape.SUPERSEDE
            ),
        ]
        outcome = apply_conflicts(payload, rendered, root=conflict_vault, now=NOW)
        assert not outcome.edits  # the rejected target is never edited
        assert len([line for line in outcome.trail_lines if "already rejected" in line]) == 1
        # The new zettel gained no supersedes link to the rejected target.
        assert _links(rendered[0].document, "supersedes") == []


class TestCorroboration:
    def test_supports_on_new_zettel_only(self, conflict_vault: Path) -> None:
        rendered = _render_one(conflict_vault, concept_type="observation")
        payload = IngestPayload()
        payload.corroborations = [CorroborationEntry(new_zettel=0, target=LinkTarget(to=ACCEPTED, claim="c1"))]
        lines = apply_corroborations(payload, rendered)
        assert _links(rendered[0].document, "supports") == [ACCEPTED]
        assert len(lines) == 1
