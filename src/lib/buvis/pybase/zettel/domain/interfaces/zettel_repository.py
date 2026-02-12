"""
This module defines an abstract base class for managing Zettel entities.

Imports:
    - :class:`abc.ABC` and :class:`abc.abstractmethod` for creating abstract base classes and methods.
    - :class:`typing.TYPE_CHECKING` for type checking support.
    - :class:`zettel.domain.entities.zettel.zettel.Zettel` for Zettel entity type annotations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel


class ZettelReader(ABC):
    """Abstract base class for reading :class:`Zettel` entities."""

    @abstractmethod
    def find_by_location(self, repository_location: str) -> Zettel:
        """
        Retrieve a :class:`Zettel` entity by its repository location.

        :param repository_location: The location in the repository to search.
        :type repository_location: str
        :return: The found Zettel entity.
        :rtype: :class:`Zettel`
        """
        pass

    @abstractmethod
    def find_all(self, directory: str, extensions: list[str] | None = None) -> list[Zettel]:
        """
        Retrieve all :class:`Zettel` entities from a directory.

        :param directory: Path to the directory to scan.
        :param extensions: File extensions to include (default: ["md"]).
        :return: A list of Zettel entities.
        :rtype: list[:class:`Zettel`]
        """
        pass


class ZettelWriter(ABC):
    """Abstract base class for writing :class:`Zettel` entities."""

    @abstractmethod
    def save(self, zettel: Zettel) -> None:
        """
        Save a :class:`Zettel` entity to the repository.

        :param zettel: The Zettel entity to save.
        :type zettel: :class:`Zettel`
        :return: None. The function modifies the repository in place.
        """
        pass

    @abstractmethod
    def find_by_id(self, zettel_id: str) -> Zettel:
        """
        Retrieve a :class:`Zettel` entity by its ID.

        :param zettel_id: The ID of the Zettel to find.
        :type zettel_id: str
        :return: The found Zettel entity.
        :rtype: :class:`Zettel`
        """
        pass


class ZettelRepository(ZettelReader, ZettelWriter):
    """Abstract base class for a repository managing :class:`Zettel` entities."""
