"""Sort tags within the metadata of a ZettelData object."""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def sort_tags(zettel_data: ZettelData) -> None:
    """Sort the tags in the metadata of the given ZettelData object.

    Args:
        zettel_data: The ZettelData object whose tags are to be sorted.

    Returns:
        None. The function modifies the `zettel_data` in place.
    """
    tags = zettel_data.metadata.get("tags")
    if tags is not None:
        zettel_data.metadata["tags"] = sorted(tags)
