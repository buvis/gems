"""Main StringOperator facade class for string manipulation.
Provides unified interface delegating to StringCaseTools, WordLevelTools, and Abbr helpers.

Example:
    >>> StringOperator.slugify("Foo Bar")
    'foo-bar'
    >>> StringOperator.camelize("foo_bar")
    'FooBar'
"""

from __future__ import annotations

import re

from buvis.pybase.formatting.string_operator.abbr import Abbr, AbbreviationInput
from buvis.pybase.formatting.string_operator.string_case_tools import StringCaseTools
from buvis.pybase.formatting.string_operator.word_level_tools import WordLevelTools


class StringOperator:
    """Facade class providing unified string manipulation operations.

    All methods are static. Delegates to StringCaseTools, WordLevelTools, Abbr.
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
        return " ".join(text.split()).rstrip().lstrip()

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
    def prepend(text: str, prepend_text: str) -> str:
        """Prepend a prefix when the text does not already start with it.

        Args:
            text: Target text.
            prepend_text: Prefix to add when missing.
        Returns:
            The original text if the prefix exists, otherwise the prefixed text.
        Example:
            >>> StringOperator.prepend("bar", "pre-")
            'pre-bar'
        """
        if text.startswith(prepend_text):
            return text

        return f"{prepend_text}{text}"

    @staticmethod
    def slugify(text: str) -> str:
        """Create a URL-safe slug from the given text.

        Args:
            text: Input text to convert.
        Returns:
            A lowercase slug with unsafe characters replaced by hyphens.
        Example:
            >>> StringOperator.slugify("Foo Bar!")
            'foo-bar'
        """
        text = str(text)
        unsafe = [
            '"',
            "#",
            "$",
            "%",
            "&",
            "+",
            ",",
            "/",
            ":",
            ";",
            "=",
            "?",
            "@",
            "[",
            "\\",
            "]",
            "^",
            "`",
            "{",
            "|",
            "}",
            "~",
            "'",
            "_",
        ]
        text = text.translate({ord(char): "-" for char in unsafe})
        text = "-".join(text.split())
        text = re.sub("-{2,}", "-", text)

        return text.lower()

    @staticmethod
    def singularize(text: str) -> str:
        """Return the singular form of the provided text.

        Args:
            text: Word to singularize.
        Returns:
            Singularized form of the word.
        Example:
            >>> StringOperator.singularize("mice")
            'mouse'
        """
        return WordLevelTools.singularize(text)

    @staticmethod
    def pluralize(text: str) -> str:
        """Return the plural form of the provided text.

        Args:
            text: Word to pluralize.
        Returns:
            Pluralized form of the word.
        Example:
            >>> StringOperator.pluralize("mouse")
            'mice'
        """
        return WordLevelTools.pluralize(text)

    @staticmethod
    def humanize(text: str) -> str:
        """Make an identifier more readable for humans.

        Args:
            text: Identifier in snake_case or camelCase.
        Returns:
            A human-readable string with spaces and capitalization.
        Example:
            >>> StringOperator.humanize("first_name")
            'First name'
        """
        return StringCaseTools.humanize(text)

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
    def as_graphql_field_name(text: str) -> str:
        """Convert text to a GraphQL-friendly PascalCase field name.

        Args:
            text: Text to normalize.
        Returns:
            A PascalCase representation suitable for GraphQL schemas.
        Example:
            >>> StringOperator.as_graphql_field_name("first_name")
            'FirstName'
        """
        return StringCaseTools.as_graphql_field_name(text)

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

    @staticmethod
    def suggest_tags(text: str, model: str, url: str = "http://localhost:11434") -> list[str]:
        """Suggest tags for text via ollama API.

        Args:
            text: Text to analyze for tag candidates.
            model: Ollama model name (e.g. "llama3.2:3b").
            url: Ollama base URL.
        Returns:
            A list of suggested tag strings, or empty list on error.
        """
        from buvis.pybase.formatting.string_operator.suggest_tags import suggest_tags

        return suggest_tags(text, model, url)
