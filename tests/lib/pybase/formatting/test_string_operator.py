from __future__ import annotations

from unittest.mock import patch

import pytest
from buvis.pybase.formatting.string_operator.string_operator import StringOperator


class TestCollapse:
    @pytest.mark.parametrize(
        ("input_", "expected"),
        [
            ("hello   world", "hello world"),
            ("  hello  ", "hello"),
            ("hello\t\nworld", "hello world"),
            ("", ""),
            ("   \t\n  ", ""),
        ],
    )
    def test_collapse(self, input_: str, expected: str) -> None:
        assert StringOperator.collapse(input_) == expected


class TestShorten:
    def test_unchanged_under_limit(self) -> None:
        assert StringOperator.shorten("short", 10, 2) == "short"

    def test_truncates_with_ellipsis(self) -> None:
        assert StringOperator.shorten("hello world", 8, 2) == "hello ...ld"

    def test_exactly_at_limit(self) -> None:
        assert StringOperator.shorten("12345", 5, 1) == "12345"

    def test_one_over_limit(self) -> None:
        assert StringOperator.shorten("123456", 5, 1) == "1234...6"

    def test_preserves_suffix_length(self) -> None:
        result = StringOperator.shorten("abcdefghij", 7, 3)
        assert result.endswith("hij")
        assert result == "abcd...hij"


class TestSlugify:
    @pytest.mark.parametrize(
        ("input_", "expected"),
        [
            ("Hello", "hello"),
            ("hello world", "hello-world"),
            ("hello@world", "hello-world"),
            ("hello---world", "hello-world"),
            ("hello   world", "hello-world"),
            ("hello_world", "hello-world"),
            ("Foo Bar", "foo-bar"),
        ],
    )
    def test_slugify(self, input_: str, expected: str) -> None:
        assert StringOperator.slugify(input_) == expected


class TestPrepend:
    @pytest.mark.parametrize(
        ("text", "prefix", "expected"),
        [
            ("bar", "pre-", "pre-bar"),
            ("pre-bar", "pre-", "pre-bar"),
            ("", "pre-", "pre-"),
            ("bar", "", "bar"),
        ],
    )
    def test_prepend(self, text: str, prefix: str, expected: str) -> None:
        assert StringOperator.prepend(text, prefix) == expected


class TestStringCaseDelegation:
    @pytest.mark.parametrize(
        ("method", "mock_path", "input_", "return_value"),
        [
            ("humanize", "StringCaseTools.humanize", "first_name", "Humanized"),
            ("underscore", "StringCaseTools.underscore", "FirstName", "first_name"),
            ("as_note_field_name", "StringCaseTools.as_note_field_name", "NoteName", "note-name"),
            ("as_graphql_field_name", "StringCaseTools.as_graphql_field_name", "note_name", "NoteName"),
            ("camelize", "StringCaseTools.camelize", "first_name", "FirstName"),
        ],
    )
    def test_delegates(self, method: str, mock_path: str, input_: str, return_value: str) -> None:
        full_path = f"buvis.pybase.formatting.string_operator.string_case_tools.{mock_path}"
        with patch(full_path, return_value=return_value) as mock:
            assert getattr(StringOperator, method)(input_) == return_value
            mock.assert_called_once_with(input_)


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
    @patch("buvis.pybase.formatting.string_operator.string_operator.Abbr.replace_abbreviations")
    def test_delegates_to_abbr(self, mock_replace) -> None:
        mock_replace.return_value = "Expanded"
        result = StringOperator.replace_abbreviations("API", [{"API": "Test"}], 2)
        assert result == "Expanded"
        mock_replace.assert_called_once_with("API", [{"API": "Test"}], 2)
