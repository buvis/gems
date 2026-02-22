from __future__ import annotations

from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.front_matter_preprocessor import (
    ZettelParserMarkdownFrontMatterPreprocessor,
)


class TestNormalizeTags:
    def test_removes_brackets_and_normalizes(self) -> None:
        text = "tags: [foo, bar, baz]"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar, baz]"

    def test_removes_hashes(self) -> None:
        text = "tags: #foo #bar #baz"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar, baz]"

    def test_removes_hashes_with_commas(self) -> None:
        text = "tags: #foo, #bar, #baz"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar, baz]"

    def test_comma_separated_no_spaces(self) -> None:
        text = "tags: foo,bar,baz"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar, baz]"

    def test_comma_separated_with_spaces(self) -> None:
        text = "tags: foo, bar, baz"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar, baz]"

    def test_space_separated(self) -> None:
        text = "tags: foo bar baz"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar, baz]"

    def test_already_correct_format(self) -> None:
        text = "tags: [foo, bar, baz]"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar, baz]"

    def test_single_tag_key(self) -> None:
        text = "tag: foo"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tag: [foo]"

    def test_single_tag_key_with_hash(self) -> None:
        text = "tag: #foo"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tag: [foo]"

    def test_empty_tags(self) -> None:
        text = "tags: "
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: []"

    def test_empty_brackets(self) -> None:
        text = "tags: []"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: []"

    def test_no_tags_line(self) -> None:
        text = "title: My Note\nstatus: active"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "title: My Note\nstatus: active"

    def test_tags_among_other_lines(self) -> None:
        text = "title: My Note\ntags: #foo #bar\nstatus: active"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "title: My Note\ntags: [foo, bar]\nstatus: active"

    def test_brackets_with_hashes(self) -> None:
        text = "tags: [#foo, #bar]"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar]"

    def test_mixed_separators(self) -> None:
        text = "tags: #foo bar, baz"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar, baz]"

    def test_single_tag(self) -> None:
        text = "tags: foo"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo]"

    def test_tags_with_extra_spaces(self) -> None:
        text = "tags:   foo   bar  "
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [foo, bar]"

    def test_does_not_match_tags_in_body_text(self) -> None:
        text = "This line mentions tags: in passing but not at start"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "This line mentions tags: in passing but not at start"

    def test_tags_at_line_start_only(self) -> None:
        text = "tags: alpha\n  tags: beta"
        result = ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)
        assert result == "tags: [alpha]\n  tags: beta"


class TestPreprocess:
    def test_delegates_to_normalize_tags(self) -> None:
        text = "tags: #a #b"
        result = ZettelParserMarkdownFrontMatterPreprocessor.preprocess(text)
        assert result == "tags: [a, b]"

    def test_plain_text_unchanged(self) -> None:
        text = "just some text"
        result = ZettelParserMarkdownFrontMatterPreprocessor.preprocess(text)
        assert result == "just some text"

    def test_multiline_with_tags(self) -> None:
        text = "title: Hello\ntags: [#x, #y]\ndate: 2024-01-01"
        result = ZettelParserMarkdownFrontMatterPreprocessor.preprocess(text)
        assert result == "title: Hello\ntags: [x, y]\ndate: 2024-01-01"
