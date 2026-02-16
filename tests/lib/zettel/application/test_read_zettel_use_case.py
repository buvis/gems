from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.zettel.application.use_cases.read_zettel_use_case import ReadZettelUseCase
from buvis.pybase.zettel.domain.entities import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelReader
from buvis.pybase.zettel.domain.interfaces.zettel_repository_exceptions import (
    ZettelRepositoryZettelNotFoundError,
)


@pytest.fixture
def mock_zettel_repository():
    return MagicMock(spec=ZettelReader)


@pytest.fixture
def read_zettel_use_case(mock_zettel_repository):
    return ReadZettelUseCase(mock_zettel_repository)


def test_read_zettel_use_case_init(mock_zettel_repository):
    use_case = ReadZettelUseCase(mock_zettel_repository)
    assert use_case.repository == mock_zettel_repository


@patch("buvis.pybase.zettel.application.use_cases.read_zettel_use_case.ZettelFactory")
def test_execute_success(mock_zettel_factory, read_zettel_use_case):
    mock_zettel = MagicMock(spec=Zettel)
    read_zettel_use_case.repository.find_by_location.return_value = mock_zettel
    mock_zettel_factory.create.return_value = mock_zettel

    result = read_zettel_use_case.execute("test_location")

    assert result == mock_zettel
    read_zettel_use_case.repository.find_by_location.assert_called_once_with("test_location")
    mock_zettel_factory.create.assert_called_once_with(mock_zettel)


def test_execute_not_found(read_zettel_use_case):
    read_zettel_use_case.repository.find_by_location.side_effect = ZettelRepositoryZettelNotFoundError

    with pytest.raises(ZettelRepositoryZettelNotFoundError):
        read_zettel_use_case.execute("non_existent_location")

    read_zettel_use_case.repository.find_by_location.assert_called_once_with("non_existent_location")
