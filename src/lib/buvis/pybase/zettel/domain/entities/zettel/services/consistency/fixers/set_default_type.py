"""
This module provides functionality to set default metadata types for ZettelData objects.

    data structure for zettel metadata."""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

DEFAULT_TYPE: str = "note"


def set_default_type(zettel_data: ZettelData) -> None:
    """
    Set the default type in the metadata of the provided :class:`ZettelData` object.

    :param zettel_data: The zettel data object to modify
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    zettel_data.metadata["type"] = DEFAULT_TYPE
