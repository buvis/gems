"""Move zkn-id metadata to id for ZettelData objects."""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def move_zkn_id_to_id(zettel_data: ZettelData) -> None:
    """Move the 'zkn-id' metadata to 'id' in the given ZettelData object.

    If 'zkn-id' exists and 'id' does not, 'zkn-id' is moved to 'id' and then 'zkn-id' is deleted.

    Args:
        zettel_data: The ZettelData object whose metadata is to be modified.

    Returns:
        None. The function modifies the `zettel_data` in place.
    """
    zkn_id = zettel_data.metadata.get("zkn-id")
    if zkn_id is not None:
        if "id" not in zettel_data.metadata:
            zettel_data.metadata["id"] = zkn_id
        del zettel_data.metadata["zkn-id"]
