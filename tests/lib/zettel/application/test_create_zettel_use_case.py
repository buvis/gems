from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import (
    CreateZettelUseCase,
)
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter
from buvis.pybase.zettel.domain.templates import ZettelTemplate
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def mock_zettel_writer():
    return MagicMock(spec=ZettelWriter)


@pytest.fixture
def create_zettel_use_case(tmp_path, mock_zettel_writer):
    return CreateZettelUseCase(tmp_path, mock_zettel_writer)


def _setup_factory_mock(mocker):
    mock_factory = mocker.patch("buvis.pybase.zettel.application.use_cases.create_zettel_use_case.ZettelFactory")
    return mock_factory


def _make_template_and_zettel(mock_factory, zettel_id="20231026120000", with_hooks=False):
    mock_template = MagicMock(spec=ZettelTemplate)
    mock_data = MagicMock(spec=ZettelData)
    mock_data.metadata = {"id": zettel_id}
    mock_data.file_path = None
    mock_data.sections = []
    mock_data.reference = {}
    mock_template.build_data.return_value = mock_data

    mock_zettel = MagicMock(spec=Zettel)
    mock_zettel.id = zettel_id
    mock_zettel.get_data.return_value = mock_data
    mock_factory.create.return_value = mock_zettel

    if with_hooks:
        mock_hook = MagicMock()
        mock_template.hooks.return_value = [mock_hook]
    else:
        mock_template.hooks.return_value = []

    return mock_template, mock_data, mock_zettel


class TestCreateZettelUseCase:
    def test_calls_writer_save(self, mocker, create_zettel_use_case, mock_zettel_writer):
        mock_factory = _setup_factory_mock(mocker)
        mock_template, mock_data, mock_zettel = _make_template_and_zettel(mock_factory)
        mock_data.metadata["title"] = "Test Zettel"

        create_zettel_use_case.execute(mock_template, {"title": "Test Zettel"})

        mock_zettel_writer.save.assert_called_once_with(mock_zettel)
        assert mock_data.file_path == str(create_zettel_use_case.zettelkasten_path / "20231026120000.md")

    def test_raises_file_exists(self, mocker, create_zettel_use_case, tmp_path):
        mock_factory = _setup_factory_mock(mocker)
        mock_template, mock_data, mock_zettel = _make_template_and_zettel(mock_factory)

        (tmp_path / "20231026120000.md").touch()

        with pytest.raises(FileExistsError):
            create_zettel_use_case.execute(mock_template, {"title": "Test Zettel"})

    def test_runs_hooks(self, mocker, create_zettel_use_case, mock_zettel_writer):
        hook_runner = MagicMock()
        create_zettel_use_case = CreateZettelUseCase(
            create_zettel_use_case.zettelkasten_path,
            mock_zettel_writer,
            hook_runner=hook_runner,
        )
        mock_factory = _setup_factory_mock(mocker)
        mock_template, mock_data, mock_zettel = _make_template_and_zettel(mock_factory, with_hooks=True)

        create_zettel_use_case.execute(mock_template, {"title": "Test Zettel"})

        hook_runner.assert_called_once_with(
            mock_template.hooks.return_value,
            mock_data,
            create_zettel_use_case.zettelkasten_path,
        )

    def test_returns_path(self, mocker, create_zettel_use_case, mock_zettel_writer):
        mock_factory = _setup_factory_mock(mocker)
        mock_template, mock_data, mock_zettel = _make_template_and_zettel(mock_factory)

        path = create_zettel_use_case.execute(mock_template, {"title": "Test Zettel"})

        expected_path = create_zettel_use_case.zettelkasten_path / "20231026120000.md"
        assert path == expected_path
