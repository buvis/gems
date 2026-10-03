"""Phase 1: MOC authoring (create + append inside the marker block)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from klyreon.ingest.moc import MEMBERS_CLOSE, MEMBERS_OPEN, ensure_moc
from klyreon.spec.validator import validate_file
from klyreon.spec.writer import write_document

pytestmark = pytest.mark.klyreon

NOW = dt.datetime(2026, 5, 1, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
MOC_REL = "wiki/mocs/architecture.md"


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "wiki" / "mocs").mkdir(parents=True)
    return root


class TestCreateMoc:
    def test_missing_moc_is_created_and_validates(self, tmp_path: Path) -> None:
        root = _vault(tmp_path)
        doc = ensure_moc(root, MOC_REL, ["wiki/notes/20260101000000.md"], now=NOW)
        assert doc.get("kind") == "moc"
        assert not validate_file(doc)
        assert MEMBERS_OPEN in doc.body
        assert MEMBERS_CLOSE in doc.body
        assert "20260101000000" in doc.body


class TestAppendPreservesProse:
    def test_prose_above_and_below_survives_two_appends(self, tmp_path: Path) -> None:
        root = _vault(tmp_path)
        # A human-authored MOC with prose around the block.
        human = (
            "---\n"
            "id: architecture\n"
            "title: Architecture\n"
            'created: "2026-01-01T09:00:00+02:00"\n'
            "kind: moc\n"
            "---\n\n"
            "# Architecture\n\n"
            "PROSE-ABOVE the human wrote this.\n\n"
            f"{MEMBERS_OPEN}\n{MEMBERS_CLOSE}\n\n"
            "PROSE-BELOW the human wrote this too.\n"
        )
        (root / MOC_REL).write_text(human, encoding="utf-8")

        doc1 = ensure_moc(root, MOC_REL, ["wiki/notes/20260101000000.md"], now=NOW)
        write_document(doc1, root / MOC_REL)
        doc2 = ensure_moc(root, MOC_REL, ["wiki/notes/20260101000001.md"], now=NOW)

        assert "PROSE-ABOVE the human wrote this." in doc2.body
        assert "PROSE-BELOW the human wrote this too." in doc2.body
        assert "20260101000000" in doc2.body
        assert "20260101000001" in doc2.body

    def test_duplicate_member_not_added_twice(self, tmp_path: Path) -> None:
        root = _vault(tmp_path)
        doc1 = ensure_moc(root, MOC_REL, ["wiki/notes/20260101000000.md"], now=NOW)
        write_document(doc1, root / MOC_REL)
        doc2 = ensure_moc(root, MOC_REL, ["wiki/notes/20260101000000.md"], now=NOW)
        # The full member-link line must appear exactly once.
        assert doc2.body.count("](wiki/notes/20260101000000.md)") == 1
