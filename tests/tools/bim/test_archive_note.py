from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bim.commands.archive_note.archive_note import (
    CommandArchiveNote,
    archive_single,
    unarchive_single,
)


@pytest.fixture
def zettel_file(tmp_path: Path) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text("# Test", encoding="utf-8")
    return p


@pytest.fixture
def repo_mocks() -> tuple[MagicMock, MagicMock, MagicMock]:
    data = MagicMock()
    data.metadata = {"type": "note"}
    data.file_path = "/tmp/source.md"
    zettel = MagicMock()
    zettel.get_data.return_value = data
    repo = MagicMock()
    repo.find_by_location.return_value = zettel
    return repo, zettel, data


class TestArchiveSingle:
    def test_archives_note(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, zettel, data = repo_mocks
        archive_dir = tmp_path / "archive"
        captured_path: list[str] = []

        with (
            patch("bim.commands.archive_note.archive_note.get_repo", return_value=repo),
            patch("bim.commands.archive_note.archive_note.UpdateZettelUseCase") as mock_update,
            patch("bim.commands.archive_note.archive_note.DeleteZettelUseCase") as mock_delete,
        ):
            mock_update.return_value.execute.side_effect = lambda z, c: captured_path.append(data.file_path)
            archive_single(zettel_file, archive_dir, quiet=True)
            mock_update.return_value.execute.assert_called_once_with(zettel, {"processed": True})
            mock_delete.return_value.execute.assert_called_once_with(zettel)
            assert captured_path[0] == str(archive_dir / zettel_file.name)

    def test_archives_project(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, zettel, data = repo_mocks
        data.metadata = {"type": "project"}
        archive_dir = tmp_path / "archive"

        with (
            patch("bim.commands.archive_note.archive_note.get_repo", return_value=repo),
            patch("bim.commands.archive_note.archive_note.UpdateZettelUseCase") as mock_update,
            patch("bim.commands.archive_note.archive_note.DeleteZettelUseCase") as mock_delete,
        ):
            archive_single(zettel_file, archive_dir, quiet=True)
            mock_update.return_value.execute.assert_called_once_with(
                zettel,
                {"processed": True, "completed": True},
            )
            mock_delete.return_value.execute.assert_called_once_with(zettel)

    def test_quiet_suppresses_console(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, _zettel, _data = repo_mocks
        archive_dir = tmp_path / "archive"

        with (
            patch("bim.commands.archive_note.archive_note.get_repo", return_value=repo),
            patch("bim.commands.archive_note.archive_note.UpdateZettelUseCase"),
            patch("bim.commands.archive_note.archive_note.DeleteZettelUseCase"),
            patch("bim.commands.archive_note.archive_note.console") as mock_console,
        ):
            archive_single(zettel_file, archive_dir, quiet=True)
            mock_console.success.assert_not_called()

    def test_loud_prints_console(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, _zettel, _data = repo_mocks
        archive_dir = tmp_path / "archive"

        with (
            patch("bim.commands.archive_note.archive_note.get_repo", return_value=repo),
            patch("bim.commands.archive_note.archive_note.UpdateZettelUseCase"),
            patch("bim.commands.archive_note.archive_note.DeleteZettelUseCase"),
            patch("bim.commands.archive_note.archive_note.console") as mock_console,
        ):
            archive_single(zettel_file, archive_dir)
            mock_console.success.assert_called_once()

    def test_returns_message(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, _zettel, _data = repo_mocks
        archive_dir = tmp_path / "archive"

        with (
            patch("bim.commands.archive_note.archive_note.get_repo", return_value=repo),
            patch("bim.commands.archive_note.archive_note.UpdateZettelUseCase"),
            patch("bim.commands.archive_note.archive_note.DeleteZettelUseCase"),
        ):
            msg = archive_single(zettel_file, archive_dir, quiet=True)
            assert zettel_file.name in msg


class TestUnarchiveSingle:
    def test_unarchives_note(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, zettel, data = repo_mocks
        zettelkasten_dir = tmp_path / "zettelkasten"
        captured_path: list[str] = []

        with (
            patch("bim.commands.archive_note.archive_note.get_repo", return_value=repo),
            patch("bim.commands.archive_note.archive_note.UpdateZettelUseCase") as mock_update,
            patch("bim.commands.archive_note.archive_note.DeleteZettelUseCase") as mock_delete,
            patch("bim.commands.archive_note.archive_note.console"),
        ):
            mock_update.return_value.execute.side_effect = lambda z, c: captured_path.append(data.file_path)
            unarchive_single(zettel_file, zettelkasten_dir)
            mock_update.return_value.execute.assert_called_once_with(zettel, {"processed": False})
            mock_delete.return_value.execute.assert_called_once_with(zettel)
            assert captured_path[0] == str(zettelkasten_dir / zettel_file.name)

    def test_unarchives_project(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, zettel, data = repo_mocks
        data.metadata = {"type": "project"}
        zettelkasten_dir = tmp_path / "zettelkasten"

        with (
            patch("bim.commands.archive_note.archive_note.get_repo", return_value=repo),
            patch("bim.commands.archive_note.archive_note.UpdateZettelUseCase") as mock_update,
            patch("bim.commands.archive_note.archive_note.DeleteZettelUseCase") as mock_delete,
            patch("bim.commands.archive_note.archive_note.console"),
        ):
            unarchive_single(zettel_file, zettelkasten_dir)
            mock_update.return_value.execute.assert_called_once_with(
                zettel,
                {"processed": False, "completed": False},
            )
            mock_delete.return_value.execute.assert_called_once_with(zettel)


class TestCommandArchiveNote:
    def test_batch_archives_all(self, tmp_path: Path) -> None:
        path_one = tmp_path / "one.md"
        path_two = tmp_path / "two.md"
        archive_dir = tmp_path / "archive"
        zettelkasten_dir = tmp_path / "zettelkasten"

        with patch("bim.commands.archive_note.archive_note.archive_single") as mock:
            cmd = CommandArchiveNote(
                paths=[path_one, path_two],
                path_archive=archive_dir,
                path_zettelkasten=zettelkasten_dir,
            )
            cmd.execute()
            mock.assert_any_call(path_one, archive_dir)
            mock.assert_any_call(path_two, archive_dir)
            assert mock.call_count == 2

    def test_undo_calls_unarchive(self, tmp_path: Path) -> None:
        path_one = tmp_path / "one.md"
        archive_dir = tmp_path / "archive"
        zettelkasten_dir = tmp_path / "zettelkasten"

        with patch("bim.commands.archive_note.archive_note.unarchive_single") as mock:
            cmd = CommandArchiveNote(
                paths=[path_one],
                path_archive=archive_dir,
                path_zettelkasten=zettelkasten_dir,
                undo=True,
            )
            cmd.execute()
            mock.assert_called_once_with(path_one, zettelkasten_dir)
