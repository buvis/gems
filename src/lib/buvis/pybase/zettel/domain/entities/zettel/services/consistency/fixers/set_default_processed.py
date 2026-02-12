"""
This module provides functionality to set default metadata values for ZettelData objects.

Imports:
    - :class:`ZettelData` from buvis.pybase.zettel.domain.value_objects.zettel_data
"""

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def set_default_processed(zettel_data: ZettelData) -> None:
    """
    Set the 'processed' metadata field of a :class:`ZettelData` object to False.

    :param zettel_data: The ZettelData object to modify
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    zettel_data.metadata["processed"] = False
