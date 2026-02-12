"""
This module defines the :class:`ZettelData` class used for managing zettelkasten data entries.

Classes:
    - :class:`ZettelData`: Manages metadata, references, and content sections of a zettel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ZettelData:
    """
    A class to represent and manage the data of a zettel in a zettelkasten system.

    This class manages metadata, references, and content sections of a zettel.
    """

    metadata: dict[str, Any] = field(default_factory=dict)
    """
    :var metadata: Stores metadata of the zettel.
    :type metadata: dict
    """

    reference: dict[str, Any] = field(default_factory=dict)
    """
    :var reference: Stores references linked to the zettel.
    :type reference: dict
    """

    sections: list[tuple[str, str]] = field(default_factory=list)
    """
    :var sections: Contains different sections of content in the zettel.
    :type sections: list
    """

    file_path: str | None = None
    """
    :var file_path: Path to the source file, if any.
    :type file_path: str | None
    """
