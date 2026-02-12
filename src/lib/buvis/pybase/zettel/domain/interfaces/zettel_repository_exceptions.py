"""
This module defines a custom exception class for handling errors related to Zettel not found in a repository.

Imports:
    - :class:`Exception` from the standard library for base exception functionality.

Classes:
    - :class:`ZettelRepositoryZettelNotFoundError`: Custom exception class for Zettel not found errors.
"""


class ZettelRepositoryZettelNotFoundError(Exception):
    """
    Exception raised when a Zettel is not found in the repository.

    :param message: Error message to be displayed.
    :type message: str
    :raises Exception: Inherits from the base :class:`Exception`.
    """

    def __init__(
        self: "ZettelRepositoryZettelNotFoundError",
        message: str = "Zettel not found in repository.",
    ) -> None:
        """
        Initialize the exception with a message.

        :param message: Custom message for the exception.
        :type message: str
        :return: None. Initializes the exception object.
        """
        super().__init__(message)
