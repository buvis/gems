from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository


def test_zettel_repository_methods():
    mock_repo = MagicMock(spec=ZettelRepository)
    mock_zettel = MagicMock()
    zettel_id = "123"
    location = "location1"

    # Test save method
    mock_repo.save(mock_zettel)
    mock_repo.save.assert_called_with(mock_zettel)

    # Test find_by_id method
    mock_repo.find_by_id(zettel_id)
    mock_repo.find_by_id.assert_called_with(zettel_id)

    # Test find_all method
    mock_repo.find_all()
    mock_repo.find_all.assert_called_once()

    # Test find_by_location method
    mock_repo.find_by_location(location)
    mock_repo.find_by_location.assert_called_with(location)
