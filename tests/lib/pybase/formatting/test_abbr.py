from __future__ import annotations

from buvis.pybase.formatting.string_operator.abbr import (
    Abbr,
    _get_abbreviations_replacements,
)


class TestAbbr:
    def test_replaces_with_provided_abbreviations(self) -> None:
        result = Abbr.replace_abbreviations(
            "Use the API and CLI",
            abbreviations=[
                {"API": "Application Programming Interface"},
                {"CLI": "Command Line Interface"},
            ],
            level=1,
        )

        assert result == "Use the Application Programming Interface and Command Line Interface"

    def test_no_abbreviations_returns_original_text(self) -> None:
        result = Abbr.replace_abbreviations("Use the API", level=1)

        assert result == "Use the API"

    def test_empty_abbreviations_list_is_ignored(self) -> None:
        result = Abbr.replace_abbreviations(
            "Use the API",
            abbreviations=[],
            level=1,
        )

        assert result == "Use the API"


class TestAbbrExpand:
    """Tests for different expansion levels."""

    def test_level_0_fixes_case_only(self) -> None:
        """Level 0 returns the abbreviation with correct case."""
        result = Abbr.replace_abbreviations(
            "Use the api",
            abbreviations=[{"API": "Application"}],
            level=0,
        )
        assert result == "Use the API"

    def test_level_2_adds_abbreviation_in_parens(self) -> None:
        """Level 2 returns short form with abbreviation in parentheses."""
        result = Abbr.replace_abbreviations(
            "Use the API",
            abbreviations=[{"API": "Application"}],
            level=2,
        )
        assert result == "Use the Application (API)"

    def test_level_2_no_parens_when_short_equals_abbr(self) -> None:
        """Level 2 skips parens when short equals abbreviation."""
        result = Abbr.replace_abbreviations(
            "Use the API",
            abbreviations=[{"API": "API"}],
            level=2,
        )
        assert result == "Use the API"

    def test_level_3_uses_long_form(self) -> None:
        """Level 3 returns the long form."""
        result = Abbr.replace_abbreviations(
            "Use API",
            abbreviations=[{"API": "App<<Application Programming Interface>>"}],
            level=3,
        )
        assert result == "Use Application Programming Interface"

    def test_level_4_long_form_with_abbr(self) -> None:
        """Level 4 returns long form with abbreviation in parentheses."""
        result = Abbr.replace_abbreviations(
            "Use API",
            abbreviations=[{"API": "App<<Application Programming Interface>>"}],
            level=4,
        )
        assert result == "Use Application Programming Interface (API)"

    def test_level_4_no_parens_when_long_equals_abbr(self) -> None:
        """Level 4 skips parens when long equals abbreviation."""
        result = Abbr.replace_abbreviations(
            "Use the API",
            abbreviations=[{"API": "API<<API>>"}],
            level=4,
        )
        assert result == "Use the API"

    def test_abbr_in_parenthesis_not_replaced(self) -> None:
        """Abbreviations followed by closing paren are not replaced."""
        result = Abbr.replace_abbreviations(
            "The (API) works",
            abbreviations=[{"API": "Application"}],
            level=1,
        )
        # Abbreviation in parens should not be replaced
        assert result == "The (API) works"


class TestGetAbbreviationsReplacements:
    """Tests for _get_abbreviations_replacements helper."""

    def test_non_dict_abbreviation_converted(self) -> None:
        """Non-dict abbreviations are converted to dict."""
        result = _get_abbreviations_replacements(["API"])
        assert "api" in result
        assert result["api"] == ("API", "API", "API")

    def test_none_expansion_uses_key(self) -> None:
        """None expansion uses the abbreviation key."""
        result = _get_abbreviations_replacements([{"API": None}])
        assert result["api"] == ("API", "API", "API")

    def test_empty_short_uses_abbr(self) -> None:
        """Empty short form uses the abbreviation."""
        result = _get_abbreviations_replacements([{"API": "<<Long Form>>"}])
        assert result["api"][0] == "API"
        assert result["api"][1] == "API"  # short = abbr when empty
        assert result["api"][2] == "Long Form"

    def test_empty_long_uses_short(self) -> None:
        """Empty long form uses the short form."""
        result = _get_abbreviations_replacements([{"API": "Short<<>>"}])
        assert result["api"][1] == "Short"
        assert result["api"][2] == "Short"  # long = short when empty

    def test_empty_abbreviations_returns_empty_dict(self) -> None:
        """Empty abbreviations list returns empty dict."""
        assert _get_abbreviations_replacements([]) == {}
        assert _get_abbreviations_replacements(None) == {}
