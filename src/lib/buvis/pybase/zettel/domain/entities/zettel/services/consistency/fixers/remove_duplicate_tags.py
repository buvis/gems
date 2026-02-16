"""Remove duplicate tags from ZettelData instances."""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def remove_duplicate_tags(zettel_data: ZettelData) -> None:
    """Remove duplicate tags from the metadata of a ZettelData instance.

    This function modifies the 'tags' list in the metadata dictionary of the provided
    ZettelData instance by converting it to a set and back to a list, thereby
    removing any duplicate entries.

    Args:
        zettel_data: The ZettelData instance whose tags are to be deduplicated.

    Returns:
        None. The function modifies the `zettel_data` in place.
    """
    tags = zettel_data.metadata.get("tags")
    if tags is not None:
        zettel_data.metadata["tags"] = list(set(tags))
