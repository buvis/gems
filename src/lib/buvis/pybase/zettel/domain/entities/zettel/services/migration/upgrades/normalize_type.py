"""
This module handles the normalization of zettel types based on predefined mappings.

    represent and manipulate zettel metadata."""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

TYPE_MIGRATIONS = {
    "loop": "project",
    "wiki-article": "note",
    "zettel": "note",
}


def normalize_type(zettel_data: ZettelData) -> None:
    """
    Normalize the type of a zettel by mapping it to a new type if applicable.

    This function checks the current type of the zettel and updates it to a new type based on
    predefined mappings. If no mapping is found, the type remains unchanged.

    :param zettel_data: The zettel data whose type is to be normalized.
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    :rtype: None
    """
    if zettel_data.metadata.get("type"):
        zettel_data.metadata["type"] = TYPE_MIGRATIONS.get(
            zettel_data.metadata["type"],
            zettel_data.metadata["type"],
        )
