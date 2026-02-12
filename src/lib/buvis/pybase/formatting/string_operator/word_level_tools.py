"""Word-level string operations.
WordLevelTools provides singularization and pluralization using the inflection library.
Certain words (e.g. minutes) are excluded from transformation.

Example:
    >>> WordLevelTools.pluralize('cat')
    'cats'
    >>> WordLevelTools.singularize('dogs')
    'dog'
"""

from inflection import pluralize as infl_pluralize
from inflection import singularize as infl_singularize


class WordLevelTools:
    """Word-level text manipulation utilities.
    Static utility class for singularization and pluralization.
    Wraps inflection library with domain-specific exceptions.
    """

    @staticmethod
    def singularize(text: str) -> str:
        """Singularize `text` unless it matches an exception like 'minutes'.

        Args:
            text: Word to singularize.

        Returns:
            Singular form of `text`, or the original `text` when it is exempted.

        Example:
            >>> WordLevelTools.singularize('minutes')
            'minutes'
            >>> WordLevelTools.singularize('dogs')
            'dog'
        """
        exceptions = ["minutes"]

        return text if text in exceptions else infl_singularize(text)

    @staticmethod
    def pluralize(text: str) -> str:
        """Pluralize `text` unless it matches an exception like 'minutes'.

        Args:
            text: Word to pluralize.

        Returns:
            Plural form of `text`, or the original `text` when it is exempted.

        Example:
            >>> WordLevelTools.pluralize('minutes')
            'minutes'
            >>> WordLevelTools.pluralize('cat')
            'cats'
        """
        exceptions = ["minutes"]

        return text if text in exceptions else infl_pluralize(text)
