"""
This module provides functionality to migrate parent reference to comply with latest standard.

It includes functions to parse parent reference and format it as a wiki-style link.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

import re


def migrate_parent_reference(zettel_data: ZettelData) -> None:
    """Migrate parent reference to comply with latest standard.

    Args:
        zettel_data: The zettel data to be processed.

    Returns:
        None. The function modifies the `zettel_data` in place.
    """
    if zettel_data.reference.get("parent"):
        match = re.search(r"\[\[(.*?)\]\]", zettel_data.reference["parent"])
        parent_link = match.group(1) if match else None
        if parent_link:
            if str(parent_link) == str(zettel_data.metadata["id"]):
                zettel_data.reference["parent"] = (
                    f"[[zettelkasten/{zettel_data.metadata['id']}|{zettel_data.metadata['title']}]]"
                )
            else:
                zettel_data.reference["parent"] = f"[[{parent_link}]]"
