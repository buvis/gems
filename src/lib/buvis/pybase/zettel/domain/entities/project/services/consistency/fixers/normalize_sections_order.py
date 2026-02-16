"""
Module for normalizing the order of sections in ZettelData objects.

This module provides functionality to reorder sections in a ZettelData object
according to a predefined structure. It ensures that specific sections appear
in a consistent order while preserving other sections.
"""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def normalize_sections_order(zettel_data: ZettelData) -> None:
    """Reorder the sections in a ZettelData object according to a predefined structure.

    This function takes a ZettelData object and rearranges its sections to ensure
    that specific sections appear in a consistent order. The main title section,
    description, log, and actions buffer are placed at the beginning in that order,
    followed by any other sections.

    Args:
        zettel_data: The ZettelData object whose sections need to be normalized.

    Returns:
        None. The function modifies the zettel_data in place.

    Raises:
        TypeError: If the input is not an instance of ZettelData.

    Note:
        This function modifies the input ZettelData object in-place.
        It does not return a new object but changes the existing one.
    """
    if not isinstance(zettel_data, ZettelData):
        raise TypeError("Expected zettel_data to be of type ZettelData")

    # Initialize list for the four expected sections plus other sections
    reordered_sections = [("", "")] * 4
    other_sections = []

    # Mapping of specific section titles to their desired order
    order_map = {"## Description": 1, "## Log": 2, "## Actions buffer": 3}

    for section in zettel_data.sections:
        title, content = section
        if title.startswith("# ") and reordered_sections[0] == ("", ""):
            reordered_sections[0] = (title, content)
        elif title in order_map:
            index = order_map[title]
            reordered_sections[index] = (title, content)
        else:
            other_sections.append((title, content))

    # Remove empty sections and add other sections
    zettel_data.sections = [sec for sec in reordered_sections if sec[0] != ""] + other_sections
