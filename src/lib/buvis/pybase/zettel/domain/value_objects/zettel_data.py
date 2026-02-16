"""Define ZettelData for managing zettelkasten data entries.

Classes:
    - ZettelData: Manages metadata, references, and content sections of a zettel.
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
    """Stores metadata of the zettel."""

    reference: dict[str, Any] = field(default_factory=dict)
    """Stores references linked to the zettel."""

    sections: list[tuple[str, str]] = field(default_factory=list)
    """Contains different sections of content in the zettel."""

    file_path: str | None = None
    """Path to the source file, if any."""
