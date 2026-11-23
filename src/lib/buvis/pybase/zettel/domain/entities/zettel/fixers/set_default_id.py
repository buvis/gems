"""Set a default ID for ZettelData objects based on metadata."""

from __future__ import annotations

from datetime import datetime, timezone

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
    date = zettel_data.metadata["date"]
    if not isinstance(date, datetime):
        raise ValueError("Invalid date format")

    if date.tzinfo is not None:
        date = date.astimezone(timezone.utc)

    try:
        zettel_data.metadata["id"] = int(date.strftime("%Y%m%d%H%M%S"))
    except ValueError as err:
        raise ValueError("Invalid ID format") from err
