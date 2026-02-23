from __future__ import annotations

from datetime import datetime, timezone

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.markdown import (
    MarkdownZettelFileParser,
)


class TestFormat:
    def test_round_trip_preserves_data(self):
        data = ZettelData(
            metadata={
                "id": 20240101120000,
                "title": "Round trip test",
                "date": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "type": "note",
                "tags": ["alpha", "beta"],
                "publish": False,
                "processed": False,
            },
            sections=[("## Content", "Some body text.")],
            reference={"parent": "[[20231231]]"},
        )

        formatted = MarkdownZettelFormatter.format(data)
        parsed = MarkdownZettelFileParser.parse(formatted)

        assert parsed.metadata["id"] == 20240101120000
        assert parsed.metadata["title"] == "Round trip test"
        assert parsed.metadata["type"] == "note"
        assert parsed.metadata["tags"] == ["alpha", "beta"]
        assert parsed.metadata["publish"] is False
        assert parsed.metadata["processed"] is False
        assert parsed.reference["parent"] == "[[20231231]]"

    def test_empty_sections(self):
        data = ZettelData(
            metadata={"title": "No content"},
            sections=[],
            reference={},
        )

        formatted = MarkdownZettelFormatter.format(data)

        assert "---" in formatted
        assert "title: No content" in formatted

    def test_empty_metadata(self):
        data = ZettelData(
            metadata={},
            sections=[("## Heading", "Body")],
            reference={},
        )

        formatted = MarkdownZettelFormatter.format(data)

        assert "---\n{}\n---" in formatted
        assert "## Heading" in formatted

    def test_empty_reference(self):
        data = ZettelData(
            metadata={"title": "No refs"},
            sections=[("## Content", "Text")],
            reference={},
        )

        formatted = MarkdownZettelFormatter.format(data)
        # Should end with empty back matter
        assert formatted.rstrip().endswith("---")

    def test_sections_ordering_preserved(self):
        data = ZettelData(
            metadata={"title": "Multi section"},
            sections=[
                ("## First", "First body"),
                ("## Second", "Second body"),
                ("## Third", "Third body"),
            ],
            reference={},
        )

        formatted = MarkdownZettelFormatter.format(data)
        first_pos = formatted.index("## First")
        second_pos = formatted.index("## Second")
        third_pos = formatted.index("## Third")
        assert first_pos < second_pos < third_pos

    def test_reference_keys_preserved(self):
        data = ZettelData(
            metadata={"title": "With refs"},
            sections=[],
            reference={
                "parent": "[[123]]",
                "source": "https://example.com",
                "empty_key": "",
            },
        )

        formatted = MarkdownZettelFormatter.format(data)

        assert "- parent:: [[123]]" in formatted
        assert "- source:: https://example.com" in formatted
        assert "- empty_key::" in formatted

    def test_metadata_key_ordering(self):
        data = ZettelData(
            metadata={
                "custom_field": "extra",
                "title": "Ordered",
                "id": 1,
                "type": "note",
                "tags": [],
                "publish": True,
                "processed": True,
                "date": datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
            },
            sections=[],
            reference={},
        )

        formatted = MarkdownZettelFormatter.format(data)

        # TOP_KEYS should appear before custom_field
        id_pos = formatted.index("id:")
        title_pos = formatted.index("title:")
        custom_pos = formatted.index("custom_field:")
        assert id_pos < title_pos < custom_pos

    def test_multiple_references_round_trip(self):
        data = ZettelData(
            metadata={"title": "Multi ref"},
            sections=[("## Notes", "Content")],
            reference={
                "parent": "[[100]]",
                "related": "[[200]]",
            },
        )

        formatted = MarkdownZettelFormatter.format(data)
        parsed = MarkdownZettelFileParser.parse(formatted)

        assert parsed.reference["parent"] == "[[100]]"
        assert parsed.reference["related"] == "[[200]]"
