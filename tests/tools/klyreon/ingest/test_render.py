"""Phase 1: render payload drafts into spec-valid documents."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from klyreon.backends.base import IngestPayload, PayloadClaim, ZettelDraft
from klyreon.ingest.render import SplitViolation, render_zettels
from klyreon.spec.validator import validate_file

pytestmark = pytest.mark.klyreon

NOW = dt.datetime(2026, 5, 1, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
ARCHIVE = "sources/archive/2026-05/article-x.md"


def _notes(tmp_path: Path) -> Path:
    notes = tmp_path / "wiki" / "notes"
    notes.mkdir(parents=True)
    return notes


class TestRenderHappy:
    def test_rendered_zettels_validate(self, tmp_path: Path) -> None:
        payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title="A thesis",
                    concept_type="thesis",
                    claims=[PayloadClaim(id="c1", statement="A plain claim.")],
                    mocs=["wiki/mocs/m.md"],
                    body="Some prose.",
                ),
            ],
        )
        rendered = render_zettels(payload, source_archive_path=ARCHIVE, notes_dir=_notes(tmp_path), now=NOW)
        assert len(rendered) == 1
        assert not validate_file(rendered[0].document)

    def test_sources_names_archive_not_inbox(self, tmp_path: Path) -> None:
        payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title="T",
                    concept_type="observation",
                    claims=[PayloadClaim(id="c1", statement="s")],
                    mocs=["wiki/mocs/m.md"],
                )
            ],
        )
        rendered = render_zettels(payload, source_archive_path=ARCHIVE, notes_dir=_notes(tmp_path), now=NOW)
        assert rendered[0].document.get("sources") == [ARCHIVE]

    def test_defaults_applied_to_concept_zettel(self, tmp_path: Path) -> None:
        payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title="T",
                    concept_type="thesis",
                    claims=[PayloadClaim(id="c1", statement="s")],
                    mocs=["wiki/mocs/m.md"],
                )
            ],
        )
        doc = render_zettels(payload, source_archive_path=ARCHIVE, notes_dir=_notes(tmp_path), now=NOW)[0].document
        assert doc.get("assent") == "tentative"
        assert doc.get("lifecycle") == "fleeting"
        assert doc.get("processed") is False

    def test_batch_ids_do_not_collide(self, tmp_path: Path) -> None:
        payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title=f"T{i}",
                    concept_type="observation",
                    claims=[PayloadClaim(id="c1", statement="s")],
                    mocs=["wiki/mocs/m.md"],
                )
                for i in range(3)
            ],
        )
        rendered = render_zettels(payload, source_archive_path=ARCHIVE, notes_dir=_notes(tmp_path), now=NOW)
        ids = {r.document.get("id") for r in rendered}
        assert len(ids) == 3


class TestSplitRule:
    def test_four_claim_zettel_fails_with_split_rule(self, tmp_path: Path) -> None:
        payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title="Too many claims",
                    concept_type="thesis",
                    claims=[PayloadClaim(id=f"c{i}", statement=f"claim {i}") for i in range(4)],
                    mocs=["wiki/mocs/m.md"],
                ),
            ],
        )
        with pytest.raises(SplitViolation, match="at most 3"):
            render_zettels(payload, source_archive_path=ARCHIVE, notes_dir=_notes(tmp_path), now=NOW)

    def test_sixty_one_line_body_fails_with_split_rule(self, tmp_path: Path) -> None:
        big_body = "\n".join(f"line {i}" for i in range(61))
        payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title="Too long",
                    concept_type="observation",
                    claims=[PayloadClaim(id="c1", statement="s")],
                    mocs=["wiki/mocs/m.md"],
                    body=big_body,
                ),
            ],
        )
        with pytest.raises(SplitViolation, match="at most 60"):
            render_zettels(payload, source_archive_path=ARCHIVE, notes_dir=_notes(tmp_path), now=NOW, max_body_lines=60)

    def test_three_claims_is_allowed(self, tmp_path: Path) -> None:
        payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title="Three claims",
                    concept_type="argument",
                    claims=[PayloadClaim(id=f"c{i}", statement=f"claim {i}") for i in range(3)],
                    mocs=["wiki/mocs/m.md"],
                ),
            ],
        )
        rendered = render_zettels(payload, source_archive_path=ARCHIVE, notes_dir=_notes(tmp_path), now=NOW)
        assert len(rendered[0].document.get("claims")) == 3
