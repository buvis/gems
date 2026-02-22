from __future__ import annotations

from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.back_matter_preprocessor import (
    ZettelParserMarkdownBackMatterPreprocessor,
)


class TestFixObsidianDataviewKeys:
    def test_converts_double_colon_to_single(self) -> None:
        text = "status:: active\npriority:: high"
        result = ZettelParserMarkdownBackMatterPreprocessor.fix_obsidian_dataview_keys(text)
        assert result == "status: active\npriority: high"

    def test_leaves_single_colon_unchanged(self) -> None:
        text = "title: My Note"
        result = ZettelParserMarkdownBackMatterPreprocessor.fix_obsidian_dataview_keys(text)
        assert result == "title: My Note"

    def test_no_colon_unchanged(self) -> None:
        text = "plain text line"
        result = ZettelParserMarkdownBackMatterPreprocessor.fix_obsidian_dataview_keys(text)
        assert result == "plain text line"


class TestQuoteUnsafeStrings:
    def test_quotes_value_with_colon(self) -> None:
        text = "url: https://example.com"
        result = ZettelParserMarkdownBackMatterPreprocessor.quote_unsafe_strings(text)
        assert result == 'url: "https://example.com"'

    def test_quotes_value_with_brackets(self) -> None:
        text = "tags: [a, b]"
        result = ZettelParserMarkdownBackMatterPreprocessor.quote_unsafe_strings(text)
        assert result == 'tags: "[a, b]"'

    def test_already_quoted_unchanged(self) -> None:
        text = 'url: "https://example.com"'
        result = ZettelParserMarkdownBackMatterPreprocessor.quote_unsafe_strings(text)
        assert result == 'url: "https://example.com"'

    def test_no_colon_unchanged(self) -> None:
        text = "plain line"
        result = ZettelParserMarkdownBackMatterPreprocessor.quote_unsafe_strings(text)
        assert result == "plain line"

    def test_colon_only_no_space(self) -> None:
        text = "key:"
        result = ZettelParserMarkdownBackMatterPreprocessor.quote_unsafe_strings(text)
        assert result == "key: "

    def test_safe_value_unchanged(self) -> None:
        text = "title: My Note"
        result = ZettelParserMarkdownBackMatterPreprocessor.quote_unsafe_strings(text)
        assert result == "title: My Note"


class TestPreprocess:
    def test_preprocess_combines_fixes(self) -> None:
        text = "status:: https://example.com"
        result = ZettelParserMarkdownBackMatterPreprocessor.preprocess(text)
        assert result == 'status: "https://example.com"'

    def test_preprocess_plain_text(self) -> None:
        text = "just text"
        result = ZettelParserMarkdownBackMatterPreprocessor.preprocess(text)
        assert result == "just text"
