from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bim.commands.archive_note.archive_note import CommandArchiveNote
from bim.params.archive_note import ArchiveNoteParams


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


class TestCommandArchiveNote:
    def test_archives_note(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, _zettel, data = repo_mocks
        data.file_path = str(zettel_file)
        archive_dir = tmp_path / "archive"
        cmd = CommandArchiveNote(
            params=ArchiveNoteParams(paths=[zettel_file]),
            path_archive=archive_dir,
            path_zettelkasten=tmp_path,
            repo=repo,
        )
        result = cmd.execute()
        assert result.success
        assert result.metadata["count"] == 1
        assert "Archived" in (result.output or "")
        assert data.metadata["processed"] is True

    def test_unarchives_project(
        self,
        zettel_file: Path,
        tmp_path: Path,
        repo_mocks: tuple[MagicMock, MagicMock, MagicMock],
    ) -> None:
        repo, _zettel, data = repo_mocks
        data.metadata = {"type": "project"}
        data.file_path = str(zettel_file)
        archive_dir = tmp_path / "archive"
        zettelkasten_dir = tmp_path / "zettelkasten"
        cmd = CommandArchiveNote(
            params=ArchiveNoteParams(paths=[zettel_file], undo=True),
            path_archive=archive_dir,
            path_zettelkasten=zettelkasten_dir,
            repo=repo,
        )
        result = cmd.execute()
        assert result.success
        assert result.metadata["count"] == 1
        assert "Unarchived" in (result.output or "")
        assert data.metadata["processed"] is False
        assert data.metadata["completed"] is False
