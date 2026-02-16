"""
This module defines an abstract base class for managing Zettel entities.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel


class ZettelReader(ABC):
    """Abstract base class for reading Zettel entities."""

    @abstractmethod
    def find_by_location(self, repository_location: str) -> Zettel:
        """Retrieve a Zettel entity by its repository location.

        Args:
            repository_location: The location in the repository to search.

        Returns:
            The found Zettel entity.
        """
        pass

    @abstractmethod
    def find_all(
        self,
        directory: str,
        metadata_eq: dict[str, Any] | None = None,
    ) -> list[Zettel]:
        """Retrieve all Zettel entities from a directory.

        Args:
            directory: Path to the directory to scan.
            metadata_eq: Optional dict of field=value eq conditions.
                Entries not matching all conditions are skipped before Zettel
                object creation.

        Returns:
            A list of Zettel entities.
        """
        pass

    @abstractmethod
    def find_by_id(self, zettel_id: str) -> Zettel:
        """Retrieve a Zettel entity by its ID.

        Args:
            zettel_id: The ID of the Zettel to find.

        Returns:
            The found Zettel entity.
        """
        pass


class ZettelWriter(ABC):
    """Abstract base class for writing Zettel entities."""

    @abstractmethod
    def save(self, zettel: Zettel) -> None:
        """Save a Zettel entity to the repository.

        Args:
            zettel: The Zettel entity to save.

        Returns:
            None. The function modifies the repository in place.
        """
        pass

    @abstractmethod
    def delete(self, zettel: Zettel) -> None:
        """Delete a Zettel entity from the repository.

        Args:
            zettel: The Zettel entity to delete.
        """
        pass


class ZettelRepository(ZettelReader, ZettelWriter):
    """Abstract base class for a repository managing Zettel entities."""
