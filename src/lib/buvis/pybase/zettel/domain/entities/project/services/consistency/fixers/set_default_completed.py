"""
This module contains a function to set the default publish status for a ZettelData object.

Imports:
    - :class:`ZettelData` from buvis.pybase.zettel.domain.value_objects.zettel_data which is used to manipulate zettel metadata.
"""

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def set_default_completed(zettel_data: ZettelData) -> None:
    """
    Set the default completed status of the zettel data to False if it isn't on gtd-list: completed.

    :param zettel_data: The ZettelData object whose completed status is to be set.
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    if not zettel_data.metadata.get("completed"):
        zettel_data.metadata["completed"] = False

        if zettel_data.metadata.get("gtd-list") and zettel_data.metadata["gtd-list"] == "completed":
            zettel_data.metadata["completed"] = True
            del zettel_data.metadata["gtd-list"]
