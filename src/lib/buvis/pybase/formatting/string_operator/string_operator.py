"""Main StringOperator facade class for string manipulation.
Provides unified interface delegating to StringCaseTools and Abbr helpers.

Example:
    >>> StringOperator.camelize("foo_bar")
    'FooBar'
"""

from __future__ import annotations

from buvis.pybase.formatting.string_operator.abbr import Abbr, AbbreviationInput
from buvis.pybase.formatting.string_operator.string_case_tools import StringCaseTools


class StringOperator:
    """Facade class providing unified string manipulation operations.

    All methods are static. Delegates to StringCaseTools and Abbr.
    """

    @staticmethod
    def collapse(text: str) -> str:
        """Collapse whitespace and strip the ends of the text.

        Args:
            text: Raw text that may contain repeated whitespace.
        Returns:
            The text with internal whitespace collapsed and trimmed.
        Example:
            >>> StringOperator.collapse("  foo   bar ")
            'foo bar'
        """
        return " ".join(text.split())

    @staticmethod
    def shorten(text: str, limit: int, suffix_length: int) -> str:
        """Truncate text while preserving a suffix and inserting ellipsis.

        Args:
            text: Text to truncate.
            limit: Maximum length of the returned string.
            suffix_length: Number of characters to keep from the end after ellipsis.
        Returns:
            A shortened string with an ellipsis if truncation occurred.
        Example:
            >>> StringOperator.shorten("short", 10, 2)
            'short'
        """
        if len(text) > limit:
            return text[: limit - suffix_length] + "..." + text[-suffix_length:]

        return text

    @staticmethod
    def underscore(text: str) -> str:
        """Convert text to snake_case.

        Args:
            text: String to convert.
        Returns:
            A snake_case version of the text.
        Example:
            >>> StringOperator.underscore("FirstName")
            'first_name'
        """
        return StringCaseTools.underscore(text)

    @staticmethod
    def as_note_field_name(text: str) -> str:
        """Convert text to a lowercase, hyphen-delimited note field name.

        Args:
            text: Text to normalize.
        Returns:
            A lowercase string with hyphen separators.
        Example:
            >>> StringOperator.as_note_field_name("Note Title")
            'note-title'
        """
        return StringCaseTools.as_note_field_name(text)

    @staticmethod
    def camelize(text: str) -> str:
        """Convert text to CamelCase.

        Args:
            text: Text to convert.
        Returns:
            A CamelCase string.
        Example:
            >>> StringOperator.camelize("first_name")
            'FirstName'
        """
        return StringCaseTools.camelize(text)

    @staticmethod
    def replace_abbreviations(
        text: str = "",
        abbreviations: list[AbbreviationInput] | None = None,
        level: int = 0,
    ) -> str:
        """Replace abbreviations within the text using configured levels.

        Args:
            text: Text containing abbreviations to replace.
            abbreviations: Mapping of abbreviations to expanded text.
            level: Expansion level (0=case fix, 4=long text plus abbreviation).
        Returns:
            The text with abbreviations expanded according to the level.
        Example:
            >>> StringOperator.replace_abbreviations(
            ...     "Send an API request",
            ...     [{"API": "Application Programming Interface<<Application Programming Interface>>"}],
            ...     level=2,
            ... )
            'Send an Application Programming Interface (API) request'
        """
        return Abbr.replace_abbreviations(text, abbreviations, level)
