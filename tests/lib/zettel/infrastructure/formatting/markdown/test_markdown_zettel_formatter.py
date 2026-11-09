from __future__ import annotations

import os
import time
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.markdown import (
    MarkdownZettelFileParser,
)


@pytest.fixture
def vault_timezone() -> Iterator[None]:
    """Run in the vault's zone: the formatter writes dates in local time, so offsets only round-trip there."""
    if not hasattr(time, "tzset"):
        pytest.skip("Controlled system timezone requires time.tzset")
    original = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Prague"
    time.tzset()
    try:
        yield
    finally:
        if original is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = original
        time.tzset()


class TestFormat:
    def test_round_trip_preserves_nested_yaml_aliases(self) -> None:
        original = """---
title: Aliases
first:
  primary: &first [one, two]
  secondary: *first
second:
  primary: &second [three, four]
  secondary: *second
---

# Aliases
"""
        data = MarkdownZettelFileParser.parse(original)

        formatted = MarkdownZettelFormatter.format(data)
        reparsed = MarkdownZettelFileParser.parse(formatted)

        assert reparsed.metadata == data.metadata
        assert MarkdownZettelFormatter.format(reparsed) == formatted

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
        assert formatted.endswith("Text\n")
        assert formatted.count("---") == 2

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


VAULT_STYLE_NOTE = """---
id: 20260105093012
title: Sourdough starter care
date: 2026-01-05T09:30:12+01:00
tags: [cooking, bread, lang/rust]
type: note
publish: false
processed: false
summary: Feed it daily
---

# Sourdough starter care

Body in Markdown.

---

- web:: [Starter basics](https://example.com/starter)
"""


class TestVaultTagShape:
    def test_writes_tags_as_flow_list_before_type(self) -> None:
        data = ZettelData(
            metadata={
                "id": 1,
                "title": "Probe",
                "date": datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
                "type": "note",
                "tags": ["zebra", "alpha"],
                "publish": False,
                "processed": False,
            },
            sections=[("# Probe", "")],
        )
        lines = MarkdownZettelFormatter.format(data).splitlines()
        assert "tags: [zebra, alpha]" in lines
        assert lines.index("tags: [zebra, alpha]") < lines.index("type: note")

    def test_writes_no_tags_as_empty_flow_list(self) -> None:
        data = ZettelData(metadata={"title": "Probe", "tags": []}, sections=[("# Probe", "")])
        assert "tags: []" in MarkdownZettelFormatter.format(data).splitlines()

    def test_keeps_a_long_tag_list_on_one_line(self) -> None:
        tags = [f"area/long-tag-name-{n}" for n in range(12)]
        data = ZettelData(metadata={"title": "Probe", "tags": tags}, sections=[("# Probe", "")])
        assert f"tags: [{', '.join(tags)}]" in MarkdownZettelFormatter.format(data).splitlines()

    @pytest.mark.usefixtures("vault_timezone")
    def test_vault_style_note_round_trips_unchanged(self) -> None:
        assert MarkdownZettelFormatter.format(MarkdownZettelFileParser.parse(VAULT_STYLE_NOTE)) == VAULT_STYLE_NOTE


MEETING_NOTE = """---
id: 20260512090000
title: 2026-05-12 | Weekly sync meeting minutes
date: 2026-05-12T09:00:00+02:00
tags: []
type: meeting-minutes
publish: false
processed: false
location: teams
start: 09:00
end: '10:00'
organizer: Ada Lovelace
attendees:
- Ada Lovelace
summary: ''
---

# 2026-05-12 | Weekly sync meeting minutes

## Log

- agreed on the plan
"""


class TestKeyOrder:
    def test_keeps_keys_after_processed_in_written_order(self) -> None:
        data = ZettelData(
            metadata={"title": "Probe", "processed": False, "location": "teams", "end": "x", "attendees": []},
            sections=[("# Probe", "")],
        )
        lines = MarkdownZettelFormatter.format(data).splitlines()
        after_processed = lines[lines.index("processed: false") + 1 :]
        assert [line.split(":")[0] for line in after_processed[:3]] == ["location", "end", "attendees"]

    @pytest.mark.usefixtures("vault_timezone")
    def test_meeting_note_round_trips_unchanged(self) -> None:
        assert MarkdownZettelFormatter.format(MarkdownZettelFileParser.parse(MEETING_NOTE)) == MEETING_NOTE


class TestStableBodyFormatting:
    def test_empty_backmatter_round_trip_is_stable(self) -> None:
        data = ZettelData(metadata={"title": "Probe"}, sections=[("# Probe", "Text")])
        formatted = MarkdownZettelFormatter.format(data)
        assert formatted.endswith("Text\n")
        assert formatted.count("---") == 2
        assert MarkdownZettelFormatter.format(MarkdownZettelFileParser.parse(formatted)) == formatted

    def test_explicit_breaks_and_fenced_code_are_preserved(self) -> None:
        body = 'Line  \nNext\n\n```json\n{\n  "value": 1\n}\n```'
        data = ZettelData(metadata={"title": "Probe"}, sections=[("# Probe", body)])
        formatted = MarkdownZettelFormatter.format(data)
        assert f"# Probe\n\n{body}\n" in formatted
        assert MarkdownZettelFormatter.format(MarkdownZettelFileParser.parse(formatted)) == formatted
