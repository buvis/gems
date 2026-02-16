"""
This module provides functionality to sort tags within the metadata of a :class:`ZettelData` object.
"""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def sort_tags(zettel_data: ZettelData) -> None:
    """
    Sort the tags in the metadata of the given :class:`ZettelData` object.

    :param zettel_data: The ZettelData object whose tags are to be sorted.
    :type zettel_data: :class:`ZettelData`
    :return: None. The function modifies the `zettel_data` in place.
    """
    tags = zettel_data.metadata.get("tags")
    if tags is not None:
        zettel_data.metadata["tags"] = sorted(tags)
