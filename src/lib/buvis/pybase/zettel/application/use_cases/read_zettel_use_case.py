"""
This module defines the ReadZettelUseCase class.

It includes functionality to read zettel from ZettelReader and returning it as
a specific zettel accourding to zettel type.
"""

from __future__ import annotations

import buvis.pybase.zettel.domain.entities as zettel_entities
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelReader
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory


class ReadZettelUseCase:
    """Read zettel from repository by location and downcast it to zettel.

    This class is responsible for taking location of a zettel within a ZettelReader, and downcasting
    it using ZettelFactory service to specific zettel according to zettel type.

    Args:
        repository: An instance of a class that implements the ZettelReader interface,
            used to data access in persistence layer.
    """

    def __init__(self: ReadZettelUseCase, repository: ZettelReader) -> None:
        """Initialize a new instance of the ReadZettelUseCase class.

        Args:
            repository: An instance of a class that implements the ZettelReader interface,
                which will be used to retrieve the data.
        """
        self.repository = repository

    def execute(
        self: ReadZettelUseCase,
        repository_location: str,
    ) -> zettel_entities.Zettel:
        """Execute the use case of reading from repository by location and downcasting to zettel.

        This method takes repository location, attempts to retrieve the corresponding zettel from the repository,
        downcasts it into a zettel, and returns it. It handles potential exceptions during the retrieval process.

        Args:
            repository_location: Unique identifier of location within repository containing zettel data.

        Raises:
            ZettelRepositoryZettelNotFoundError: If the zettel is not found in the repository.

        Returns:
            A Zettel object created from the retrieved zettel.
        """
        zettel = self.repository.find_by_location(repository_location)
        return ZettelFactory.create(zettel)
