from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
)
from pytest_mock import MockerFixture


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

    @patch(
        "buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter.MarkdownZettelFormatter.format"
    )
    def test_save_propagates_atomic_write_failure_and_leaves_file_unchanged(
        self,
        mock_format,
        mocker: MockerFixture,
        repository,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "zettel.md"
        original_content = "original zettel content"
        file_path.write_text(original_content, encoding="utf-8")

        zettel_data = ZettelData(file_path=str(file_path))
        zettel = MagicMock(spec=Zettel)
        zettel.get_data.return_value = zettel_data
        mock_format.return_value = "new formatted content"

        # Force os.replace (the swap step) to fail; the target must remain unchanged
        # and the exception must propagate to the caller.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("simulated swap failure"),
        )

        with pytest.raises(OSError):
            repository.save(zettel)

        # Verify the file remains unchanged (no partial write, no corruption)
        assert file_path.read_text(encoding="utf-8") == original_content


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
        repository_with_path.find_by_location.assert_called_once_with(str(tmp_path / "20250101120000.md"))

    def test_find_by_id_raises_without_zettelkasten_path(self, repository) -> None:
        with pytest.raises(ValueError):
            repository.find_by_id("20250101120000")
