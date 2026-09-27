from __future__ import annotations

import pytest
from buvis.pybase.formatting.string_operator.string_case_tools import StringCaseTools


class TestUnderscore:
    @pytest.mark.parametrize(
        ("input_", "expected"),
        [
            ("SomeValue", "some_value"),
            ("someValue", "some_value"),
            ("some_value", "some_value"),
            ("HTMLParser", "html_parser"),
        ],
    )
    def test_underscore(self, input_: str, expected: str) -> None:
        assert StringCaseTools.underscore(input_) == expected


class TestAsNoteFieldName:
    @pytest.mark.parametrize(
        ("input_", "expected"),
        [
            ("SomeValue", "some-value"),
            ("someValue", "some-value"),
            ("some-value", "some-value"),
            ("SOME_VALUE", "some-value"),
        ],
    )
    def test_as_note_field_name(self, input_: str, expected: str) -> None:
        assert StringCaseTools.as_note_field_name(input_) == expected


class TestCamelize:
    @pytest.mark.parametrize(
        ("input_", "expected"),
        [
            ("user_name", "UserName"),
            ("some-name", "SomeName"),
            ("first-name_last", "FirstNameLast"),
            ("name", "Name"),
        ],
    )
    def test_camelize(self, input_: str, expected: str) -> None:
        assert StringCaseTools.camelize(input_) == expected
