"""Abbreviation expansion utilities.

The :class:`Abbr` class expands abbreviations with configurable levels
(0=fix case, 1=short, 2=short+abbr, 3=long, 4=long+abbr).

Example:
    Abbr.replace_abbreviations(
        "Send an API request",
        [{"API": "Application Programming Interface<<Application Programming Interface>>"}],
        level=2,
    )
"""

from __future__ import annotations

import re

abbr_pattern = r"\b(\w+)\b(?!\s*\))"

AbbreviationInput = dict[str, str | None] | str
AbbreviationReplacements = dict[str, tuple[str, str, str]]


class Abbr:
    """Abbreviation replacement utility.

    Provides static methods for expanding abbreviations in text with configurable expansion levels.
    """

    @staticmethod
    def replace_abbreviations(
        text: str = "",
        abbreviations: list[AbbreviationInput] | None = None,
        level: int = 0,
    ) -> str:
        """Expand abbreviations found in the provided text.

        Args:
            text: The text to process.
            abbreviations: A list of dictionaries that map abbreviations to
                expansion strings, where an expansion can include an optional
                long form delimited by ``<<`` and ``>>`` (e.g.
                ``{"API": "App<<Application Programming Interface>>"}``).
            level: Determines how much of the expansion to use (0=fix case,
                1=short, 2=short+(abbr), 3=long, 4=long+(abbr)).

        Returns:
            A string where each abbreviation is replaced according to level.

        Example::

            >>> Abbr.replace_abbreviations("Use the API", [{"API": "App"}], 1)
            'Use the App'
        """
        if abbreviations is None:
            abbreviations = []

        replacements = _get_abbreviations_replacements(abbreviations)

        # Replace occurrences of the abbreviation that are whole words
        # Replacement depends on the level:
        # 0: just fix the abbreviation case
        # 1: replace with expanded short text
        # 2: replace with expanded short text followed by abbreviation in paranthesis
        # 3: replace with expanded long text
        # 4: replace with expanded long text followed by abbreviation in paranthesis

        def replace_by_level(match: re.Match[str]) -> str:
            abbr = match.group(1)
            if abbr.lower() not in replacements:
                return abbr

            abbr_correct, short, long = replacements[abbr.lower()]

            match level:
                case 0:
                    return abbr_correct
                case 1:
                    return short
                case 2:
                    return f"{short} ({abbr_correct})" if short != abbr_correct else short
                case 3:
                    return long
                case _:
                    return f"{long} ({abbr_correct})" if long != abbr_correct else long

        return re.sub(abbr_pattern, replace_by_level, text)


def _get_abbreviations_replacements(
    abbreviations: list[AbbreviationInput] | None = None,
) -> AbbreviationReplacements:
    """Parse abbreviation definitions into replacement metadata.

    Args:
        abbreviations: List of abbreviation definitions in the same expansion format accepted by
            ``replace_abbreviations`` (each mapping an abbreviation to a string that can include
            a long form wrapped in ``<<``/``>>``).

    Returns:
        A dict mapping the lowercase abbreviation to a tuple of (original abbreviation, short expansion,
        long expansion).
    """
    if not abbreviations:
        return {}

    replacements: AbbreviationReplacements = {}

    for abbreviation in abbreviations:
        abbreviation_dict: dict[str, str | None]
        if not isinstance(abbreviation, dict):
            abbreviation_dict = {abbreviation: abbreviation}
        else:
            abbreviation_dict = abbreviation

        for abbr, expansion in abbreviation_dict.items():
            short_long_expansion_pattern = r"^(?P<short>[^<]*)(?:<<(?P<long>[^>]*)>>)?$"
            if expansion is None:
                match = re.match(short_long_expansion_pattern, abbr)
            else:
                match = re.match(short_long_expansion_pattern, expansion)

            if match:
                short = match.group("short").strip()
                long = match.group("long")
                if long:
                    long = long.strip()
            else:
                short = abbr
                long = abbr

            if short is None or short == "":
                short = abbr

            if long is None or long == "":
                long = short
            replacements[abbr.lower()] = (abbr, short, long)

    return replacements
