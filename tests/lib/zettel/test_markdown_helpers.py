from __future__ import annotations

import pytest
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.helpers import (
    extract_metadata,
    extract_reference,
    normalize_dict_keys,
    split_content_into_sections,
)


class TestExtractMetadata:
    def test_valid_front_matter(self):
        content = "---\ntitle: Test\ntype: note\n---\n\nBody."
        metadata, remaining = extract_metadata(content)
        assert metadata is not None
        assert metadata["title"] == "Test"
        assert "Body." in remaining
        assert "---" not in remaining

    def test_no_front_matter(self):
        content = "Just body text."
        metadata, remaining = extract_metadata(content)
        assert metadata is None
        assert remaining == content

    def test_empty_front_matter(self):
        content = "---\n\n---\n\nBody."
        metadata, remaining = extract_metadata(content)
        assert metadata == {}
        assert "Body." in remaining

    def test_malformed_yaml_raises(self):
        content = "---\ntitle: [unclosed\n---\n\nBody."
        with pytest.raises(ValueError, match="Failed to parse metadata"):
            extract_metadata(content)

    def test_tags_normalized(self):
        content = "---\ntags: #foo, #bar\n---\n\nBody."
        metadata, _ = extract_metadata(content)
        assert metadata is not None
        assert metadata["tags"] == ["foo", "bar"]


class TestExtractReference:
    def test_no_reference_section(self):
        content = "## Heading\n\nBody text."
        ref, remaining = extract_reference(content)
        assert ref is None
        assert remaining == content

    def test_single_reference(self):
        content = "## Content\n\nBody.\n\n---\n- source: https://example.com"
        ref, remaining = extract_reference(content)
        assert ref is not None
        assert ref["source"] == "https://example.com"
        assert "---" not in remaining

    def test_duplicate_keys_become_list(self):
        content = "## Content\n\nBody.\n\n---\n- source: https://a.com\n- source: https://b.com"
        ref, remaining = extract_reference(content)
        assert ref is not None
        assert ref["source"] == ["https://a.com", "https://b.com"]

    def test_triple_duplicate_keys_appends(self):
        content = (
            "## Content\n\nBody.\n\n---\n- source: https://a.com\n- source: https://b.com\n- source: https://c.com"
        )
        ref, _ = extract_reference(content)
        assert ref is not None
        assert ref["source"] == ["https://a.com", "https://b.com", "https://c.com"]

    def test_dataview_key_colon_stripped(self):
        content = "## Content\n\nBody.\n\n---\n- source:: https://example.com"
        ref, _ = extract_reference(content)
        assert ref is not None
        assert "source" in ref

    def test_malformed_reference_yaml_raises(self):
        content = "## Content\n\nBody.\n\n---\n[invalid: yaml: ["
        with pytest.raises(ValueError, match="Failed to parse reference"):
            extract_reference(content)

    def test_remaining_content_stripped(self):
        content = "## Content\n\nBody.\n\n---\n- link: https://example.com"
        _, remaining = extract_reference(content)
        assert remaining.rstrip() == remaining
        assert "link" not in remaining


class TestNormalizeDictKeys:
    def test_converts_keys(self):
        data = {"SomeValue": "value", "AnotherValue": 42}
        result = normalize_dict_keys(data)
        assert "some-value" in result
        assert "another-value" in result
        assert result["some-value"] == "value"
        assert result["another-value"] == 42

    def test_empty_dict(self):
        assert normalize_dict_keys({}) == {}

    def test_already_normalized(self):
        data = {"title": "Test", "type": "note"}
        result = normalize_dict_keys(data)
        assert result == data


class TestSplitContentIntoSections:
    def test_single_heading(self):
        content = "## Heading\n\nBody text.\n"
        sections = split_content_into_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == "## Heading"
        assert "Body text." in sections[0][1]

    def test_multiple_headings(self):
        content = "## First\n\nFirst body.\n\n## Second\n\nSecond body.\n"
        sections = split_content_into_sections(content)
        assert len(sections) == 2
        assert sections[0][0] == "## First"
        assert "First body." in sections[0][1]
        assert sections[1][0] == "## Second"
        assert "Second body." in sections[1][1]

    def test_no_headings(self):
        content = "Just plain text."
        sections = split_content_into_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == ""
        assert sections[0][1] == "Just plain text."

    def test_empty_content(self):
        sections = split_content_into_sections("")
        assert len(sections) == 1
        assert sections[0] == ("", "")

    def test_different_heading_levels(self):
        content = "# H1\n\nBody1.\n\n### H3\n\nBody3.\n"
        sections = split_content_into_sections(content)
        assert len(sections) == 2
        assert sections[0][0] == "# H1"
        assert sections[1][0] == "### H3"
