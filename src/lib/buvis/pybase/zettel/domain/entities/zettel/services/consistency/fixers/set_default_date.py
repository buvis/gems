"""
This module sets default dates for ZettelData objects using the datetime module.

- datetime: For fetching the current date and time in UTC.
- ZettelData: A domain value object from the zettel.domain.value_objects package."""

from __future__ import annotations

from datetime import datetime, timezone

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def set_default_date(zettel_data: ZettelData) -> None:
    """Set the default date in the metadata of a ZettelData object to the current UTC time.

    Args:
        zettel_data: The ZettelData object to modify

    Returns:
        None. The function modifies the `zettel_data` in place.
    """
    if zettel_data.metadata.get("date") is None:
        zettel_data.metadata["date"] = datetime.now(timezone.utc).replace(microsecond=0)
