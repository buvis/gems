from __future__ import annotations

from unittest.mock import MagicMock, patch

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


@patch("buvis.pybase.zettel.application.use_cases.create_zettel_use_case.ZettelFactory")
def test_execute_calls_writer_save(mock_zettel_factory, create_zettel_use_case, mock_zettel_writer):
    mock_template = MagicMock(spec=ZettelTemplate)
    mock_data = MagicMock(spec=ZettelData)
    mock_data.metadata = {"id": "20231026120000", "title": "Test Zettel"}
    mock_data.file_path = None
    mock_data.sections = []
    mock_data.reference = {}
    mock_template.build_data.return_value = mock_data
    mock_template.hooks.return_value = []

    mock_zettel = MagicMock(spec=Zettel)
    mock_zettel.id = "20231026120000"
    mock_zettel.get_data.return_value = mock_data

    mock_zettel_factory.create.return_value = mock_zettel

    answers = {"title": "Test Zettel"}
    create_zettel_use_case.execute(mock_template, answers)

    mock_zettel_writer.save.assert_called_once_with(mock_zettel)
    assert mock_data.file_path == str(create_zettel_use_case.zettelkasten_path / "20231026120000.md")


@patch("buvis.pybase.zettel.application.use_cases.create_zettel_use_case.ZettelFactory")
def test_execute_raises_file_exists(mock_zettel_factory, create_zettel_use_case, tmp_path):
    mock_template = MagicMock(spec=ZettelTemplate)
    mock_data = MagicMock(spec=ZettelData)
    mock_data.metadata = {"id": "20231026120000"}
    mock_data.sections = []
    mock_data.reference = {}
    mock_template.build_data.return_value = mock_data

    mock_zettel = MagicMock(spec=Zettel)
    mock_zettel.id = "20231026120000"
    mock_zettel_factory.create.return_value = mock_zettel

    # Create the file beforehand
    (tmp_path / "20231026120000.md").touch()

    answers = {"title": "Test Zettel"}

    with pytest.raises(FileExistsError):
        create_zettel_use_case.execute(mock_template, answers)


@patch("buvis.pybase.zettel.application.use_cases.create_zettel_use_case.ZettelFactory")
def test_execute_runs_hooks(mock_zettel_factory, create_zettel_use_case, mock_zettel_writer):
    hook_runner = MagicMock()
    create_zettel_use_case = CreateZettelUseCase(
        create_zettel_use_case.zettelkasten_path,
        mock_zettel_writer,
        hook_runner=hook_runner,
    )
    mock_template = MagicMock(spec=ZettelTemplate)
    mock_data = MagicMock(spec=ZettelData)
    mock_data.metadata = {"id": "20231026120000"}
    mock_data.file_path = None
    mock_data.sections = []
    mock_data.reference = {}
    mock_template.build_data.return_value = mock_data

    mock_hook = MagicMock()
    mock_template.hooks.return_value = [mock_hook]

    mock_zettel = MagicMock(spec=Zettel)
    mock_zettel.id = "20231026120000"
    mock_zettel.get_data.return_value = mock_data

    mock_zettel_factory.create.return_value = mock_zettel

    answers = {"title": "Test Zettel"}
    create_zettel_use_case.execute(mock_template, answers)

    hook_runner.assert_called_once_with(
        mock_template.hooks.return_value,
        mock_data,
        create_zettel_use_case.zettelkasten_path,
    )


@patch("buvis.pybase.zettel.application.use_cases.create_zettel_use_case.ZettelFactory")
def test_execute_returns_path(mock_zettel_factory, create_zettel_use_case, mock_zettel_writer):
    mock_template = MagicMock(spec=ZettelTemplate)
    mock_data = MagicMock(spec=ZettelData)
    mock_data.metadata = {"id": "20231026120000"}
    mock_data.file_path = None
    mock_data.sections = []
    mock_data.reference = {}
    mock_template.build_data.return_value = mock_data
    mock_template.hooks.return_value = []

    mock_zettel = MagicMock(spec=Zettel)
    mock_zettel.id = "20231026120000"
    mock_zettel.get_data.return_value = mock_data

    mock_zettel_factory.create.return_value = mock_zettel

    answers = {"title": "Test Zettel"}
    path = create_zettel_use_case.execute(mock_template, answers)

    expected_path = create_zettel_use_case.zettelkasten_path / "20231026120000.md"
    assert path == expected_path
