"""
This module defines the ReadZettelUseCase class.

It includes functionality to read zettel from ZettelRepository and returning it as
a specific zettel accourding to zettel type.
"""

import buvis.pybase.zettel.domain.entities as zettel_entities
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository
from buvis.pybase.zettel.domain.interfaces.zettel_repository_exceptions import (
    ZettelRepositoryZettelNotFoundError,
)
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory


class ReadZettelUseCase:
    """
    A use case class for reading zettel from repository by location and downcasting it to zettel.

    This class is responsible for taking location of a zettel within a ZettelRepository, and downcasting
    it using ZettelFactory service to specific zettel according to zettel type.

    :param repository: An instance of a class that implements the ZettelRepository interface,
                      used to data access in persistence layer.
    :type repository: ZettelRepository
    """

    def __init__(self: "ReadZettelUseCase", repository: ZettelRepository) -> None:
        """
        Initialize a new instance of the ReadZettelUseCase class.

        :param reposiroty: An instance of a class that implements the ZettelRepository interface,
                          which will be used to retrieve the data.
        :type repository: ZettelRepository
        """
        self.repository = repository

    def execute(
        self: "ReadZettelUseCase",
        repository_location: str,
    ) -> zettel_entities.Zettel:
        """
        Execute the use case of reading from repository by location and downcasting to zettel.

        This method takes repository location, attempts to retrieve the corresponding zettel from the repository,
        downcasts it into a zettel, and returns it. It handles potential exceptions during the retrieval process.

        :param repository_location: Unique identifier of location within repository containing zettel data.
        :type repository_location: str
        :raises ZettelRepositoryZettelNotFoundError: If the zettel is not found in the repository.
        :return: A Zettel object created from the retrieved zettel.
        :rtype: Zettel or its subclass
        """
        try:
            zettel = self.repository.find_by_location(repository_location)
        except ZettelRepositoryZettelNotFoundError as e:
            raise e
        if zettel is None:
            raise ZettelRepositoryZettelNotFoundError
        return ZettelFactory.create(zettel)
