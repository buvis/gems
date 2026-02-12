"""
This module provides functionality to format the title of a ZettelData object.

Imports:
- :class:`StringOperator` from the `buvis.pybase.formatting` module, used for text
  manipulation.
- :class:`ZettelData` from the `zettel.domain.value_objects.zettel_data` module,
  representing the data structure for zettel information.
"""

from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def fix_title_format(zettel_data: ZettelData) -> None:
    """
    Format the title of the given :class:`ZettelData` object.

    This function modifies the 'title' field of the :class:`ZettelData` metadata dictionary in place,
    using the :class:`StringOperator` to replace abbreviations at a specified level, removes
    unnecessary blanks and capitalizes the first letter.

    :param zettel_data: The ZettelData object whose title is to be formatted.
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    title = zettel_data.metadata["title"]
    fixed_title = StringOperator.replace_abbreviations(
        text=title,
        level=0,
    )
    fixed_title = fixed_title.lstrip().rstrip()
    fixed_title = fixed_title[0].upper() + fixed_title[1:]
    zettel_data.metadata["title"] = fixed_title
