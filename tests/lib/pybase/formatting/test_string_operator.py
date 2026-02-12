from __future__ import annotations

from unittest.mock import patch

from buvis.pybase.formatting.string_operator.string_operator import StringOperator


class TestCollapse:
    def test_collapses_multiple_spaces(self) -> None:
        assert StringOperator.collapse("hello   world") == "hello world"

    def test_strips_leading_trailing(self) -> None:
        assert StringOperator.collapse("  hello  ") == "hello"

    def test_handles_tabs_and_newlines(self) -> None:
        assert StringOperator.collapse("hello\t\nworld") == "hello world"

    def test_empty_string(self) -> None:
        assert StringOperator.collapse("") == ""

    def test_only_whitespace(self) -> None:
        assert StringOperator.collapse("   \t\n  ") == ""


class TestShorten:
    def test_unchanged_under_limit(self) -> None:
        assert StringOperator.shorten("short", 10, 2) == "short"

    def test_truncates_with_ellipsis(self) -> None:
        # prefix = text[:limit - suffix_length], ellipsis, suffix = text[-suffix_length:]
        assert StringOperator.shorten("hello world", 8, 2) == "hello ...ld"

    def test_exactly_at_limit(self) -> None:
        assert StringOperator.shorten("12345", 5, 1) == "12345"

    def test_one_over_limit(self) -> None:
        # prefix = text[:5-1] = text[:4] = "1234", suffix = text[-1] = "6"
        assert StringOperator.shorten("123456", 5, 1) == "1234...6"

    def test_preserves_suffix_length(self) -> None:
        # prefix = text[:7-3] = text[:4] = "abcd", suffix = text[-3:] = "hij"
        result = StringOperator.shorten("abcdefghij", 7, 3)
        assert result.endswith("hij")
        assert result == "abcd...hij"


class TestSlugify:
    def test_lowercases(self) -> None:
        assert StringOperator.slugify("Hello") == "hello"

    def test_replaces_spaces_with_hyphens(self) -> None:
        assert StringOperator.slugify("hello world") == "hello-world"

    def test_removes_unsafe_chars(self) -> None:
        # @ is in unsafe list, replaced with -
        assert StringOperator.slugify("hello@world") == "hello-world"

    def test_collapses_multiple_hyphens(self) -> None:
        assert StringOperator.slugify("hello---world") == "hello-world"

    def test_handles_multiple_spaces(self) -> None:
        assert StringOperator.slugify("hello   world") == "hello-world"

    def test_replaces_underscores(self) -> None:
        assert StringOperator.slugify("hello_world") == "hello-world"

    def test_complex_input(self) -> None:
        assert StringOperator.slugify("Foo Bar") == "foo-bar"


class TestPrepend:
    def test_adds_prefix_when_missing(self) -> None:
        assert StringOperator.prepend("bar", "pre-") == "pre-bar"

    def test_skips_existing_prefix(self) -> None:
        assert StringOperator.prepend("pre-bar", "pre-") == "pre-bar"

    def test_empty_text(self) -> None:
        assert StringOperator.prepend("", "pre-") == "pre-"

    def test_empty_prefix(self) -> None:
        assert StringOperator.prepend("bar", "") == "bar"


class TestStringCaseDelegation:
    @patch("buvis.pybase.formatting.string_operator.string_case_tools.StringCaseTools.humanize")
    def test_humanize_delegates(self, mock_humanize) -> None:
        mock_humanize.return_value = "Humanized"
        assert StringOperator.humanize("first_name") == "Humanized"
        mock_humanize.assert_called_once_with("first_name")

    @patch("buvis.pybase.formatting.string_operator.string_case_tools.StringCaseTools.underscore")
    def test_underscore_delegates(self, mock_underscore) -> None:
        mock_underscore.return_value = "first_name"
        assert StringOperator.underscore("FirstName") == "first_name"
        mock_underscore.assert_called_once_with("FirstName")

    @patch("buvis.pybase.formatting.string_operator.string_case_tools.StringCaseTools.as_note_field_name")
    def test_as_note_field_name_delegates(self, mock_note_field) -> None:
        mock_note_field.return_value = "note-name"
        assert StringOperator.as_note_field_name("NoteName") == "note-name"
        mock_note_field.assert_called_once_with("NoteName")

    @patch("buvis.pybase.formatting.string_operator.string_case_tools.StringCaseTools.as_graphql_field_name")
    def test_as_graphql_field_name_delegates(self, mock_graphql_field) -> None:
        mock_graphql_field.return_value = "NoteName"
        assert StringOperator.as_graphql_field_name("note_name") == "NoteName"
        mock_graphql_field.assert_called_once_with("note_name")

    @patch("buvis.pybase.formatting.string_operator.string_case_tools.StringCaseTools.camelize")
    def test_camelize_delegates(self, mock_camelize) -> None:
        mock_camelize.return_value = "FirstName"
        assert StringOperator.camelize("first_name") == "FirstName"
        mock_camelize.assert_called_once_with("first_name")


class TestPluralize:
    def test_regular_word(self) -> None:
        assert StringOperator.pluralize("cat") == "cats"

    def test_irregular_word(self) -> None:
        assert StringOperator.pluralize("mouse") == "mice"

    def test_minutes_exception(self) -> None:
        assert StringOperator.pluralize("minutes") == "minutes"


class TestSingularize:
    def test_regular_word(self) -> None:
        assert StringOperator.singularize("cats") == "cat"

    def test_irregular_word(self) -> None:
        assert StringOperator.singularize("mice") == "mouse"

    def test_minutes_exception(self) -> None:
        assert StringOperator.singularize("minutes") == "minutes"


class TestReplaceAbbreviationsDelegation:
    """Test replace_abbreviations delegates to Abbr."""

    @patch("buvis.pybase.formatting.string_operator.string_operator.Abbr.replace_abbreviations")
    def test_delegates_to_abbr(self, mock_replace) -> None:
        mock_replace.return_value = "Expanded"
        result = StringOperator.replace_abbreviations("API", [{"API": "Test"}], 2)
        assert result == "Expanded"
        mock_replace.assert_called_once_with("API", [{"API": "Test"}], 2)


class TestSuggestTags:
    """Test suggest_tags method."""

    @patch("buvis.pybase.formatting.string_operator.string_operator.TagSuggester")
    def test_limits_results(self, mock_suggester_cls) -> None:
        """Lines 258-260: suggest_tags slices result to limit_count."""
        mock_suggester = mock_suggester_cls.return_value
        mock_suggester.suggest.return_value = ["tag1", "tag2", "tag3", "tag4", "tag5"]

        result = StringOperator.suggest_tags("some text", limit_count=2)
        assert len(result) == 2
        assert result == ["tag1", "tag2"]

    @patch("buvis.pybase.formatting.string_operator.string_operator.TagSuggester")
    def test_default_limit(self, mock_suggester_cls) -> None:
        mock_suggester = mock_suggester_cls.return_value
        mock_suggester.suggest.return_value = ["t" + str(i) for i in range(15)]

        result = StringOperator.suggest_tags("text")
        assert len(result) == 10  # Default limit

    @patch("buvis.pybase.formatting.string_operator.string_operator.TagSuggester")
    def test_fewer_than_limit(self, mock_suggester_cls) -> None:
        mock_suggester = mock_suggester_cls.return_value
        mock_suggester.suggest.return_value = ["only", "two"]

        result = StringOperator.suggest_tags("text", limit_count=10)
        assert len(result) == 2
