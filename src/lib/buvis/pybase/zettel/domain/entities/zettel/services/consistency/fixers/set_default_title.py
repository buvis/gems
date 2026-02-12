"""
This module provides functionality to set default titles for ZettelData objects.

Imports:
    - :class:`ZettelData` from buvis.pybase.zettel.domain.value_objects.zettel_data
"""

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

DEFAULT_TITLE: str = "Unknown title"


def set_default_title(zettel_data: ZettelData) -> None:
    """
    Set a default title for the given ZettelData object if no title is present.

    If the ZettelData object has sections and the first section starts with '# ',
    it sets the title to the text following this marker. If no title is found,
    it sets the title to a default value.

    :param zettel_data: The ZettelData object to modify
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    if zettel_data.metadata.get("title") is None:
        first_heading = zettel_data.sections[0][0] if zettel_data.sections else ""
        if first_heading.startswith("# "):
            zettel_data.metadata["title"] = first_heading[2:]
        else:
            zettel_data.metadata["title"] = DEFAULT_TITLE
