"""Define custom exceptions for Zettel repository lookup failures.

Classes:
    - ZettelRepositoryZettelNotFoundError: Custom exception class for Zettel not found errors.
"""

from __future__ import annotations


class ZettelRepositoryZettelNotFoundError(Exception):
    """Exception raised when a Zettel is not found in the repository.

    Args:
        message: Error message to be displayed.

    Raises:
        Exception: Inherits from the base Exception.
    """

    def __init__(
        self: ZettelRepositoryZettelNotFoundError,
        message: str = "Zettel not found in repository.",
    ) -> None:
        """Initialize the exception with a message.

        Args:
            message: Custom message for the exception.

        Returns:
            None. Initializes the exception object.
        """
        super().__init__(message)
