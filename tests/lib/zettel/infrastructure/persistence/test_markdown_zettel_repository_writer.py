from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
)


@pytest.fixture
def repository() -> MarkdownZettelRepository:
    return MarkdownZettelRepository()


@pytest.fixture
def repository_with_path(tmp_path) -> MarkdownZettelRepository:
    return MarkdownZettelRepository(zettelkasten_path=tmp_path)


class TestSave:
    @patch(
        "buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter.MarkdownZettelFormatter.format"
    )
    def test_save_writes_formatted_content(self, mock_format, repository, tmp_path) -> None:
        file_path = tmp_path / "zettel.md"
        zettel_data = ZettelData(file_path=str(file_path))
        zettel = MagicMock(spec=Zettel)
        zettel.get_data.return_value = zettel_data
        mock_format.return_value = "formatted content"

        repository.save(zettel)

        assert file_path.read_text(encoding="utf-8") == "formatted content"

    def test_save_raises_without_file_path(self, repository) -> None:
        zettel_data = ZettelData()
        zettel = MagicMock(spec=Zettel)
        zettel.get_data.return_value = zettel_data

        with pytest.raises(ValueError):
            repository.save(zettel)


class TestDelete:
    def test_delete_removes_file(self, repository, tmp_path) -> None:
        file_path = tmp_path / "zettel.md"
        file_path.write_text("content")
        zettel_data = ZettelData(file_path=str(file_path))
        zettel = MagicMock(spec=Zettel)
        zettel.get_data.return_value = zettel_data

        repository.delete(zettel)

        assert not file_path.exists()

    def test_delete_raises_without_file_path(self, repository) -> None:
        zettel_data = ZettelData()
        zettel = MagicMock(spec=Zettel)
        zettel.get_data.return_value = zettel_data

        with pytest.raises(ValueError):
            repository.delete(zettel)


class TestFindById:
    def test_find_by_id_delegates_to_find_by_location(
        self,
        repository_with_path,
        tmp_path,
    ) -> None:
        expected = MagicMock(spec=Zettel)
        repository_with_path.find_by_location = MagicMock(return_value=expected)

        result = repository_with_path.find_by_id("20250101120000")

        assert result == expected
        repository_with_path.find_by_location.assert_called_once_with(
            str(tmp_path / "20250101120000.md")
        )

    def test_find_by_id_raises_without_zettelkasten_path(self, repository) -> None:
        with pytest.raises(ValueError):
            repository.find_by_id("20250101120000")
