"""
This module sets default dates for ZettelData objects using the datetime module.

Imports:
- datetime: For fetching the current date and time in UTC.
- :class:`ZettelData`: A domain value object from the zettel.domain.value_objects package.
"""

from datetime import UTC, datetime

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def set_default_date(zettel_data: ZettelData) -> None:
    """
    Set the default date in the metadata of a :class:`ZettelData` object to the current UTC time.

    :param zettel_data: The ZettelData object to modify
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    if zettel_data.metadata.get("date") is None:
        zettel_data.metadata["date"] = datetime.now(UTC).replace(microsecond=0)
