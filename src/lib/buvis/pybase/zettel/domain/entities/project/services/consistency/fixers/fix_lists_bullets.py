"""
Module for fixing list bullets in ZettelData objects.

This module provides functionality to convert asterisk-based list bullets to hyphen-based bullets in ZettelData objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def fix_lists_bullets(zettel_data: ZettelData) -> None:
    """
    Fix list bullets in the given ZettelData object.

    Convert asterisk-based list bullets to hyphen-based bullets in all sections of the ZettelData object.

    :param zettel_data: The ZettelData object to modify
    :type zettel_data: :class:`zettel.domain.value_objects.zettel_data.ZettelData`

    :return: None
    :rtype: None

    :raises: No exceptions are explicitly raised
    """
    zettel_data.sections = [
        (
            section[0],
            "\n".join(
                f"- {line[2:].strip()}" if line.startswith("* ") else line.strip() for line in section[1].split("\n")
            ),
        )
        for section in zettel_data.sections
    ]
