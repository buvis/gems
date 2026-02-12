from __future__ import annotations

from buvis.pybase.formatting.string_operator.word_level_tools import WordLevelTools


class TestSingularize:
    def test_singularizes_regular_plural(self) -> None:
        assert WordLevelTools.singularize("cats") == "cat"
        assert WordLevelTools.singularize("dogs") == "dog"
        assert WordLevelTools.singularize("users") == "user"

    def test_preserves_exception_word_minutes(self) -> None:
        assert WordLevelTools.singularize("minutes") == "minutes"

    def test_handles_irregular_plural(self) -> None:
        assert WordLevelTools.singularize("children") == "child"
        assert WordLevelTools.singularize("people") == "person"


class TestPluralize:
    def test_pluralizes_regular_singular(self) -> None:
        assert WordLevelTools.pluralize("cat") == "cats"
        assert WordLevelTools.pluralize("dog") == "dogs"
        assert WordLevelTools.pluralize("user") == "users"

    def test_preserves_exception_word_minutes(self) -> None:
        assert WordLevelTools.pluralize("minutes") == "minutes"

    def test_handles_irregular_singular(self) -> None:
        assert WordLevelTools.pluralize("child") == "children"
        assert WordLevelTools.pluralize("person") == "people"
