from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from buvis.pybase.result import CommandResult
from bim.commands.show_note.show_note import CommandShowNote


@pytest.fixture
def zettel_file(tmp_path: Path, minimal_zettel: str) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text(minimal_zettel, encoding="utf-8")
    return p


class TestCommandShowNote:
    def test_execute_returns_formatted_content(self, zettel_file: Path) -> None:
        repo = MagicMock()
        note = MagicMock()
        note.get_data.return_value = {"title": "Test Note"}
        repo.find_by_location.return_value = note
        formatter = MagicMock()
        formatter.format.return_value = "formatted content"

        cmd = CommandShowNote(paths=[zettel_file], repo=repo, formatter=formatter)
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is True
        assert result.output == "formatted content"
        assert result.warnings == []
        assert result.metadata == {"count": 1}
        repo.find_by_location.assert_called_once_with(str(zettel_file))
        formatter.format.assert_called_once_with(note.get_data.return_value)

    def test_execute_missing_path_returns_failure(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.md"
        repo = MagicMock()
        formatter = MagicMock()

        cmd = CommandShowNote(paths=[missing], repo=repo, formatter=formatter)
        result = cmd.execute()

        assert result.success is False
        assert result.output is None
        assert result.error == f"{missing} doesn't exist"
        assert result.warnings == [f"{missing} doesn't exist"]
        repo.find_by_location.assert_not_called()
        formatter.format.assert_not_called()

    def test_execute_mixed_paths_returns_warning(
        self,
        zettel_file: Path,
        tmp_path: Path,
    ) -> None:
        missing = tmp_path / "missing.md"
        repo = MagicMock()
        note = MagicMock()
        note.get_data.return_value = {"title": "Test Note"}
        repo.find_by_location.return_value = note
        formatter = MagicMock()
        formatter.format.return_value = "formatted content"

        cmd = CommandShowNote(paths=[zettel_file, missing], repo=repo, formatter=formatter)
        result = cmd.execute()

        assert result.success is True
        assert result.output == "formatted content"
        assert result.warnings == [f"{missing} doesn't exist"]
        assert result.metadata == {"count": 1}
        repo.find_by_location.assert_called_once_with(str(zettel_file))
