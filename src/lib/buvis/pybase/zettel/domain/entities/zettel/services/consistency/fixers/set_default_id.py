"""
This module provides functionality to set a default ID for :class:`ZettelData` objects based on their metadata.
"""

from __future__ import annotations

from datetime import UTC

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def set_default_id(zettel_data: ZettelData) -> None:
    """
    Set a default ID for the given :class:`ZettelData` object based on its metadata date.

    :param zettel_data: The ZettelData object to modify
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    :raises ValueError: If the ID conversion fails or if the date isn't a date.
    """
    try:
        id_str: str = zettel_data.metadata["date"].astimezone(UTC).strftime("%Y%m%d%H%M%S")
    except AttributeError as err:
        raise ValueError("Invalid date format") from err

    try:
        zettel_data.metadata["id"] = int(id_str)
    except ValueError as err:
        raise ValueError("Invalid ID format") from err
