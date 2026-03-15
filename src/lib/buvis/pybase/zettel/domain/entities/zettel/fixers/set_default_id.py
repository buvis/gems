"""Set a default ID for ZettelData objects based on metadata."""

from __future__ import annotations

from datetime import timezone

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def set_default_id(zettel_data: ZettelData) -> None:
    """Set a default ID for the given ZettelData object based on its metadata date.

    Args:
        zettel_data: The ZettelData object to modify

    Returns:
        None. The function modifies the `zettel_data` in place.

    Raises:
        ValueError: If the ID conversion fails or if the date isn't a date.
    """
    try:
        id_str: str = zettel_data.metadata["date"].astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
    except AttributeError as err:
        raise ValueError("Invalid date format") from err

    try:
        zettel_data.metadata["id"] = int(id_str)
    except ValueError as err:
        raise ValueError("Invalid ID format") from err
