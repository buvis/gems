from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.interfaces.zettel_repository import (
    ZettelReader,
    ZettelRepository,
    ZettelWriter,
)


def test_zettel_reader_methods():
    mock_reader = MagicMock(spec=ZettelReader)
    location = "location1"

    mock_reader.find_by_location(location)
    mock_reader.find_by_location.assert_called_with(location)

    mock_reader.find_all()
    mock_reader.find_all.assert_called_once()


def test_zettel_writer_methods():
    mock_writer = MagicMock(spec=ZettelWriter)
    mock_zettel = MagicMock()
    zettel_id = "123"

    mock_writer.save(mock_zettel)
    mock_writer.save.assert_called_with(mock_zettel)

    mock_writer.find_by_id(zettel_id)
    mock_writer.find_by_id.assert_called_with(zettel_id)


def test_zettel_repository_methods():
    mock_repo = MagicMock(spec=ZettelRepository)
    mock_zettel = MagicMock()
    zettel_id = "123"
    location = "location1"

    mock_repo.save(mock_zettel)
    mock_repo.save.assert_called_with(mock_zettel)

    mock_repo.find_by_id(zettel_id)
    mock_repo.find_by_id.assert_called_with(zettel_id)

    mock_repo.find_all()
    mock_repo.find_all.assert_called_once()

    mock_repo.find_by_location(location)
    mock_repo.find_by_location.assert_called_with(location)
