from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bim.commands.delete_note.delete_note import CommandDeleteNote


@pytest.fixture
def zettel_file(tmp_path: Path) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text("# Test", encoding="utf-8")
    return p


def _make_repo_for_delete(zettel_file: Path) -> MagicMock:
    data = MagicMock()
    data.file_path = str(zettel_file)
    zettel = MagicMock()
    zettel.get_data.return_value = data
    repo = MagicMock()
    repo.find_by_location.return_value = zettel

    def _delete(target) -> None:
        Path(target.get_data().file_path).unlink()

    repo.delete.side_effect = _delete
    return repo


class TestCommandDeleteNote:
    def test_deletes_file(self, zettel_file: Path) -> None:
        repo = _make_repo_for_delete(zettel_file)
        cmd = CommandDeleteNote(paths=[zettel_file], repo=repo)
        result = cmd.execute()
        assert result.success
        assert result.metadata["deleted_count"] == 1
        assert not zettel_file.exists()

    def test_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        repo = MagicMock()
        cmd = CommandDeleteNote(paths=[missing], repo=repo)
        result = cmd.execute()
        assert not result.success
        assert f"{missing} doesn't exist" in result.warnings
        repo.find_by_location.assert_not_called()
