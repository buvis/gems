"""String case conversion utilities for converting between naming conventions."""

from inflection import camelize as infl_camelize
from inflection import humanize as infl_humanize
from inflection import underscore as infl_underscore


class StringCaseTools:
    """String case conversion utilities.

    Static utility class for converting strings between naming
    conventions. Wraps the inflection library with BUVIS-specific
    field naming conventions.
    """

    @staticmethod
    def humanize(text: str) -> str:
        """Turn an identifier into a human-readable phrase.

        Args:
            text: Lowercase string or identifier to make human readable.

        Returns:
            Human-readable string with spaces and capitalized words.

        Example:
            >>> StringCaseTools.humanize('some_value')
            'Some value'
        """
        return infl_humanize(text)

    @staticmethod
    def underscore(text: str) -> str:
        """Convert a string into snake_case.

        Args:
            text: Text to convert.

        Returns:
            Snake_case version of the input text.

        Example:
            >>> StringCaseTools.underscore('SomeValue')
            'some_value'
        """
        return infl_underscore(text)

    @staticmethod
    def as_note_field_name(text: str) -> str:
        """Make a string safe for note field names (kebab-case).

        Args:
            text: Text to convert into a note field identifier.

        Returns:
            Kebab-case representation of the input text.

        Example:
            >>> StringCaseTools.as_note_field_name('SomeValue')
            'some-value'
        """
        return StringCaseTools.underscore(text).replace("_", "-").lower()

    @staticmethod
    def as_graphql_field_name(text: str) -> str:
        """Convert a string to a GraphQL-style field name (PascalCase).

        Args:
            text: Text to convert into PascalCase.

        Returns:
            PascalCase string suitable for GraphQL fields.

        Example:
            >>> StringCaseTools.as_graphql_field_name('some_value')
            'SomeValue'
        """
        return StringCaseTools.camelize(text)

    @staticmethod
    def camelize(text: str) -> str:
        """Convert a string into CamelCase, respecting hyphen separators.

        Args:
            text: Text containing hyphens or underscores.

        Returns:
            CamelCase representation of the input text.

        Example:
            >>> StringCaseTools.camelize('some-name')
            'SomeName'
        """
        text = text.replace("-", "_")

        return infl_camelize(text)
