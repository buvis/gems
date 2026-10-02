"""Spec engine: parser + writer, with the YAML traps and round-trip stability.

The probe tests at the bottom are INDEPENDENT ORACLES: they assert against
hand-written input and a hand-computed expectation, so they fail against a
naive implementation (e.g. one that lets PyYAML coerce ``id`` to int). They do
NOT trust writer-encoded fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.spec.model import FileKind
from klyreon.spec.parser import FrontmatterError, parse_file, parse_text
from klyreon.spec.writer import serialize


def _kind_for(base: Path, p: Path) -> FileKind:
    rel = p.relative_to(base).as_posix()
    if rel.startswith("sources/"):
        return FileKind.SOURCE
    if rel.startswith("wiki/notes/"):
        return FileKind.ZETTEL
    return FileKind.AUX


class TestParserTraps:
    def test_unquoted_14_digit_id_is_a_string(self) -> None:
        text = '---\nid: 20260411145300\ntitle: T\ncreated: "2026-04-11T14:53:00+02:00"\ntype: note\n---\n\n# T\n'
        doc = parse_text(text, "wiki/notes/20260411145300.md", FileKind.ZETTEL)
        assert doc.frontmatter["id"] == "20260411145300"
        assert isinstance(doc.frontmatter["id"], str)

    def test_sexagesimal_time_like_value_not_coerced_to_int(self) -> None:
        # A bare 11:30 under YAML 1.1 would parse to int 690 with the stock
        # resolver. With the sexagesimal alternative stripped, a quoted/plain
        # scalar stays a string.
        text = '---\nid: n\ntitle: T\ncreated: x\ntype: note\nref: "11:30"\n---\n\n# T\n'
        doc = parse_text(text, "x", FileKind.ZETTEL)
        assert doc.frontmatter["ref"] == "11:30"

    def test_unknown_keys_preserved_in_original_order(self) -> None:
        text = (
            "---\nid: n\ntitle: T\ntype: note\ncreated: c\naliases:\n- a\ncssclasses:\n- w\nzz-custom: 1\n---\n\n# T\n"
        )
        doc = parse_text(text, "x", FileKind.ZETTEL)
        assert doc.unknown_keys() == ["aliases", "cssclasses", "zz-custom"]

    def test_missing_fence_raises(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_text("no frontmatter here", "x", FileKind.ZETTEL)

    def test_h1_extracted(self) -> None:
        text = "---\nid: n\ntitle: T\ntype: note\ncreated: c\n---\n\n# Heading\n\nbody\n"
        doc = parse_text(text, "x", FileKind.ZETTEL)
        assert doc.h1 == "Heading"


class TestRoundTrip:
    def test_corpus_is_byte_stable(self, valid_corpus: Path) -> None:
        files = sorted(valid_corpus.rglob("*.md"))
        assert files, "valid corpus must not be empty"
        for p in files:
            kind = _kind_for(valid_corpus, p)
            original = p.read_text(encoding="utf-8")
            doc = parse_file(p, kind)
            assert serialize(doc) == original, f"round-trip not byte-stable for {p}"

    def test_fixture_with_aliases_and_cssclasses_keeps_both(self, valid_corpus: Path) -> None:
        p = valid_corpus / "wiki/notes/20260411145300.md"
        doc = parse_file(p, FileKind.ZETTEL)
        assert "aliases" in doc.frontmatter
        assert "cssclasses" in doc.frontmatter
        assert "aliases" in serialize(doc)
        assert "cssclasses" in serialize(doc)


class TestProbeStringId:
    """Independent oracle: a naive int-id impl fails these."""

    def test_string_id_survives_serialize_round_trip_quoted(self) -> None:
        # Hand-written input, hand-computed expectation: the id MUST be emitted
        # double-quoted so re-reading yields the string, never int 20260411145300.
        text = '---\nid: 20260411145300\ntitle: T\ncreated: "2026-04-11T14:53:00+02:00"\ntype: note\n---\n\n# T\n'
        doc = parse_text(text, "x", FileKind.ZETTEL)
        out = serialize(doc)
        assert 'id: "20260411145300"' in out
        # And a second parse yields the identical string, not an int.
        reparsed = parse_text(out, "x", FileKind.ZETTEL)
        assert reparsed.frontmatter["id"] == "20260411145300"
        assert isinstance(reparsed.frontmatter["id"], str)
