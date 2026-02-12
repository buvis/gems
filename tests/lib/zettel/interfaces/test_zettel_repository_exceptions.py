import pytest

from buvis.pybase.zettel.domain.interfaces.zettel_repository_exceptions import (
    ZettelRepositoryZettelNotFoundError,
)


def test_zettel_repository_zettel_not_found_error():
    """
    Test the ZettelRepositoryZettelNotFoundError to ensure it raises with the correct message.
    """
    with pytest.raises(ZettelRepositoryZettelNotFoundError) as exc_info:
        raise ZettelRepositoryZettelNotFoundError("Test error message")
    assert str(exc_info.value) == "Test error message", "The error message should match the one provided"
