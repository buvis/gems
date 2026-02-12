"""
This module defines the :class:`ZettelData` class used for managing zettelkasten data entries.

Classes:
    - :class:`ZettelData`: Manages metadata, references, and content sections of a zettel.
"""

from __future__ import annotations

from typing import Any


class ZettelData:
    """
    A class to represent and manage the data of a zettel in a zettelkasten system.

    This class manages metadata, references, and content sections of a zettel.
    """

    metadata: dict[str, Any] = {}  # noqa: RUF012
    """
    :var metadata: Stores metadata of the zettel.
    :type metadata: dict
    """

    reference: dict[str, Any] = {}  # noqa: RUF012
    """
    :var reference: Stores references linked to the zettel.
    :type reference: dict
    """

    sections: list[tuple[str, str]] = []  # noqa: RUF012
    """
    :var sections: Contains different sections of content in the zettel.
    :type sections: list
    """

    file_path: str | None = None  # noqa: RUF012
    """
    :var file_path: Path to the source file, if any.
    :type file_path: str | None
    """

    def __init__(self) -> None:
        """Initialize a new instance of :class:`ZettelData`."""
        self.metadata = {}
        self.reference = {}
        self.sections = []
        self.file_path = None
