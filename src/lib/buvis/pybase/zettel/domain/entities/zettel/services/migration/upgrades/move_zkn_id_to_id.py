"""
This module contains the function move_zkn_id_to_id which is used to modify the metadata of a
:class:`ZettelData` object by moving the value from 'zkn-id' to 'id'.

Imports:
    - :class:`ZettelData` from buvis.pybase.zettel.domain.value_objects.zettel_data
"""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def move_zkn_id_to_id(zettel_data: ZettelData) -> None:
    """
    Move the 'zkn-id' metadata to 'id' in the given :class:`ZettelData` object.

    If 'zkn-id' exists and 'id' does not, 'zkn-id' is moved to 'id' and then 'zkn-id' is deleted.

    :param zettel_data: The ZettelData object whose metadata is to be modified.
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    zkn_id = zettel_data.metadata.get("zkn-id")
    if zkn_id is not None:
        if "id" not in zettel_data.metadata:
            zettel_data.metadata["id"] = zkn_id
        del zettel_data.metadata["zkn-id"]
