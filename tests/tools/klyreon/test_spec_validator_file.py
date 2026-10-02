"""File-level validation: one invalid case per rule, each firing exactly its rule."""

from __future__ import annotations

from typing import Any

from klyreon.spec.model import Document, FileKind
from klyreon.spec.validator import validate_file


def _zettel(**overrides: Any) -> Document:
    front: dict[str, Any] = {
        "id": "20260411145300",
        "title": "A thesis",
        "created": "2026-04-11T14:53:00+02:00",
        "type": "note",
        "concept-type": "thesis",
        "assent": "tentative",
        "lifecycle": "fleeting",
        "claims": [{"id": "c1", "statement": "x"}],
    }
    front.update(overrides)
    body = overrides.pop("_body", "\n# A thesis\n")
    return Document(
        path="wiki/notes/20260411145300.md",
        kind=FileKind.ZETTEL,
        frontmatter=front,
        body=body,
        h1="A thesis",
    )


def _rules(doc: Document) -> set[str]:
    return {e.rule for e in validate_file(doc)}


class TestValidBaseline:
    def test_valid_concept_zettel_has_no_errors(self) -> None:
        assert validate_file(_zettel()) == []

    def test_valid_utility_zettel_has_no_errors(self) -> None:
        doc = Document(
            path="wiki/notes/20260408180230.md",
            kind=FileKind.ZETTEL,
            frontmatter={
                "id": "20260408180230",
                "title": "Snip",
                "created": "2026-04-08T18:02:30+02:00",
                "type": "snippet",
            },
            body="\n# Snip\n",
            h1="Snip",
        )
        assert validate_file(doc) == []


class TestFileLevelRules:
    """Each mutation triggers exactly its own rule (and no other)."""

    def test_missing_required_field(self) -> None:
        doc = _zettel()
        del doc.frontmatter["title"]
        doc.h1 = None
        doc.body = "\nbody no h1 but zero h1 is its own rule\n"
        # Removing title also removes the h1-title comparison; use a one-H1 body.
        doc.body = "\n# placeholder\n"
        rules = _rules(doc)
        assert "required-field" in rules

    def test_id_filename_mismatch(self) -> None:
        # id differs from the filename stem (20260411145300) -> that rule fires.
        rules = _rules(_zettel(id="99999999999999"))
        assert "id-filename-mismatch" in rules

    def test_zettel_id_not_14_digits(self) -> None:
        doc = _zettel(id="abc")
        doc.path = "wiki/notes/abc.md"
        assert "zettel-id-format" in _rules(doc)

    def test_created_disagrees_with_id(self) -> None:
        assert "id-created-mismatch" in _rules(_zettel(created="2026-04-11T14:53:59+02:00"))

    def test_two_h1(self) -> None:
        doc = _zettel()
        doc.body = "\n# A thesis\n\n# second\n"
        assert "h1-exactly-one" in _rules(doc)

    def test_h1_title_mismatch(self) -> None:
        doc = _zettel()
        doc.body = "\n# different\n"
        doc.h1 = "different"
        assert "h1-title-mismatch" in _rules(doc)

    def test_type_species_zettel_gets_source_type(self) -> None:
        assert "type-species" in _rules(_zettel(type="article"))

    def test_concept_type_enum(self) -> None:
        doc = _zettel(**{"concept-type": "nonsense", "claims": [{"id": "c1", "statement": "x"}]})
        assert "concept-type-enum" in _rules(doc)

    def test_assent_enum(self) -> None:
        assert "assent-enum" in _rules(_zettel(assent="maybe"))

    def test_lifecycle_enum(self) -> None:
        assert "lifecycle-enum" in _rules(_zettel(lifecycle="ancient"))

    def test_claims_required_on_thesis(self) -> None:
        doc = _zettel()
        del doc.frontmatter["claims"]
        assert "claims-required" in _rules(doc)

    def test_aporia_must_not_carry_claims(self) -> None:
        assert "aporia-no-claims" in _rules(_zettel(**{"concept-type": "aporia"}))

    def test_claim_missing_statement(self) -> None:
        assert "claim-shape" in _rules(_zettel(claims=[{"id": "c1"}]))

    def test_doubt_shape(self) -> None:
        assert "doubt-shape" in _rules(_zettel(doubts=[{"mode": "regress"}]))

    def test_doubt_mode_enum(self) -> None:
        assert "doubt-mode-enum" in _rules(
            _zettel(doubts=[{"mode": "bogus", "claim": None, "rationale": "r"}]),
        )

    def test_disagreement_target_shape(self) -> None:
        assert "doubt-target-shape" in _rules(
            _zettel(
                doubts=[{"mode": "disagreement", "claim": "c1", "rationale": "r", "target": {"to": "x"}}],
            ),
        )

    def test_link_rel_enum(self) -> None:
        assert "link-rel-enum" in _rules(_zettel(links=[{"rel": "frobnicates", "to": "wiki/notes/x.md"}]))

    def test_link_shape(self) -> None:
        assert "link-shape" in _rules(_zettel(links=[{"rel": "supports"}]))

    def test_publish_true_rejected(self) -> None:
        assert "publish-true" in _rules(_zettel(publish=True))

    def test_concept_field_on_source_document(self) -> None:
        doc = Document(
            path="sources/2026-04/article-x.md",
            kind=FileKind.SOURCE,
            frontmatter={
                "id": "article-x",
                "title": "X",
                "created": "2026-04-01T00:00:00+02:00",
                "type": "article",
                "assent": "tentative",
            },
            body="\n# X\n",
            h1="X",
        )
        assert "concept-field-on-source" in _rules(doc)

    def test_aux_kind_enum(self) -> None:
        doc = Document(
            path="wiki/mocs/architecture.md",
            kind=FileKind.AUX,
            frontmatter={"id": "architecture", "title": "A", "created": "2026-01-01T00:00:00+02:00", "kind": "nope"},
            body="\n# A\n",
            h1="A",
        )
        assert "aux-kind-enum" in _rules(doc)
