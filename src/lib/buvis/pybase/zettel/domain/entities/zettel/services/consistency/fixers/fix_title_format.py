"""
This module provides functionality to format the title of a ZettelData object.

- StringOperator from the `buvis.pybase.formatting` module, used for text
  manipulation.
- ZettelData from the `zettel.domain.value_objects.zettel_data` module,
  representing the data structure for zettel information."""

from __future__ import annotations

from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def fix_title_format(zettel_data: ZettelData) -> None:
    """Format the title of the given ZettelData object.

    This function modifies the 'title' field of the ZettelData metadata dictionary in place,
    using the StringOperator to replace abbreviations at a specified level, removes
    unnecessary blanks and capitalizes the first letter.

    Args:
        zettel_data: The ZettelData object whose title is to be formatted.

    Returns:
        None. The function modifies the `zettel_data` in place.
    """
    title = zettel_data.metadata["title"]
    fixed_title = StringOperator.replace_abbreviations(
        text=title,
        level=0,
    )
    fixed_title = fixed_title.lstrip().rstrip()
    fixed_title = fixed_title[0].upper() + fixed_title[1:]
    zettel_data.metadata["title"] = fixed_title
