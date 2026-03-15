"""
This module provides functionality to align the first heading of a Zettel (a type of note) to its
title.

    the data structure of a Zettel."""

from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def align_h1_to_title(zettel_data: ZettelData) -> None:
    """Align the first heading of the Zettel to match its title from metadata.

    This function ensures the first section of the Zettel starts with a heading that matches the Zettel's title.
    If the first section does not start with a heading or the heading is different, it adjusts or
    inserts the correct heading.

    Args:
        zettel_data: The Zettel data to be modified.

    Returns:
        None. The function modifies the `zettel_data` in place.
    """
    title_heading = f"# {zettel_data.metadata['title']}"

    if zettel_data.sections:
        first_heading, content = zettel_data.sections[0]

        if not first_heading.startswith("# ") or first_heading != title_heading:
            zettel_data.sections[0] = (title_heading, content)
    else:
        zettel_data.sections.append((title_heading, ""))
