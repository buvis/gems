"""
This module provides functionality to set default metadata values for ZettelData objects.

Imports:
    - :class:`ZettelData` from buvis.pybase.zettel.domain.value_objects.zettel_data
"""

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def set_default_tags(zettel_data: ZettelData) -> None:
    """
    Set the 'tags' metadata field of a :class:`ZettelData` object to empty list.

    This function modifies the input ZettelData object in-place by creating an
    empty list for the "tags" key in its metadata dictionary.

    :param zettel_data: The ZettelData object to modify
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    try:
        zettel_data.metadata["tags"] = []
    except AttributeError as err:
        raise AttributeError("ZettelData object does not have a metadata attribute") from err
    except TypeError as err:
        raise TypeError("ZettelData.metadata is not a mutable mapping") from err
