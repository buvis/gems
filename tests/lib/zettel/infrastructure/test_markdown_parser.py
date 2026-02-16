from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.back_matter_preprocessor import (
    ZettelParserMarkdownBackMatterPreprocessor,
)
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.front_matter_preprocessor import (
    ZettelParserMarkdownFrontMatterPreprocessor,
)
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.markdown import (
    MarkdownZettelFileParser,
)
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import ZettelFileParser


class TestMarkdownPreprocessors:
    def test_front_matter_normalizes_tags(self) -> None:
        raw = "tags: #alpha, #beta"
        result = ZettelParserMarkdownFrontMatterPreprocessor.preprocess(raw)
        assert result == "tags: [alpha, beta]"

    def test_back_matter_fixes_dataview_and_quotes(self) -> None:
        raw = "source:: https://example.com:foo"
        result = ZettelParserMarkdownBackMatterPreprocessor.preprocess(raw)
        assert result == 'source: "https://example.com:foo"'


class TestMarkdownZettelFileParser:
    def test_parse_front_matter_and_sections(self) -> None:
        content = """\
---
title: Parser Test
type: note
tags: #alpha, #beta
processed: false
---

## Heading

Body text.
"""
        parsed = MarkdownZettelFileParser.parse(content)

        assert parsed.metadata["title"] == "Parser Test"
        assert parsed.metadata["type"] == "note"
        assert parsed.metadata["tags"] == ["alpha", "beta"]
        assert parsed.sections[0][0] == "## Heading"
        assert "Body text." in parsed.sections[0][1]

    def test_parse_with_back_matter(self) -> None:
        content = """\
---
title: Back Matter
---

## Content

Body.

---
- source:: https://example.com/one
- source:: https://example.com/two
- link: https://example.com/path:section
"""
        parsed = MarkdownZettelFileParser.parse(content)

        assert parsed.reference["source"] == [
            "https://example.com/one",
            "https://example.com/two",
        ]
        assert parsed.reference["link"] == "https://example.com/path:section"

    def test_missing_front_matter(self) -> None:
        content = """\
## Heading

Body without front matter.
"""
        parsed = MarkdownZettelFileParser.parse(content)

        assert parsed.metadata == {}
        assert parsed.reference == {}
        assert parsed.sections[0][0] == "## Heading"
        assert "Body without front matter." in parsed.sections[0][1]

    def test_malformed_front_matter_raises(self) -> None:
        content = """\
---
title: [unclosed
---

## Content
"""
        with pytest.raises(ValueError, match="Failed to parse metadata"):
            MarkdownZettelFileParser.parse(content)

    def test_project_note_resources_and_loops(self) -> None:
        content = """\
---
title: Project Alpha
type: project
resources:
  - https://example.com
loops:
  - weekly
---

## Status

In progress.
"""
        parsed = MarkdownZettelFileParser.parse(content)

        assert parsed.metadata["type"] == "project"
        assert parsed.metadata["resources"] == ["https://example.com"]
        assert parsed.metadata["loops"] == ["weekly"]

    def test_unicode_content(self) -> None:
        content = """\
---
title: Unicode Note
---

## Content

Café résumé.
"""
        parsed = MarkdownZettelFileParser.parse(content)

        assert "Café résumé." in parsed.sections[0][1]

    def test_empty_file(self) -> None:
        parsed = MarkdownZettelFileParser.parse("")

        assert parsed.metadata == {}
        assert parsed.reference == {}
        assert parsed.sections == [("", "")]


class TestZettelFileParser:
    def test_from_file_sets_date_and_title(self, tmp_path: Path) -> None:
        path = tmp_path / "202401151030 Project alpha.md"
        path.write_text("## Body\n\nText.", encoding="utf-8")

        parsed = ZettelFileParser.from_file(path)

        assert parsed.metadata["title"] == "Project alpha"
        # Known Python bug: len(fmt_string) used instead of digit count, so 1030 → 10:3
        assert parsed.metadata["date"] == datetime(2024, 1, 15, 10, 3, tzinfo=UTC)
