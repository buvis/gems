from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from bim.commands.delete_note.delete_note import CommandDeleteNote, delete_single


@pytest.fixture
def zettel_file(tmp_path: Path) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text("# Test", encoding="utf-8")
    return p


class TestDeleteSingle:
    def test_deletes_file(self, zettel_file: Path) -> None:
        assert zettel_file.is_file()
        delete_single(zettel_file, quiet=True)
        assert not zettel_file.exists()

    def test_returns_message(self, zettel_file: Path) -> None:
        msg = delete_single(zettel_file, quiet=True)
        assert zettel_file.name in msg

    def test_quiet_suppresses_console(self, zettel_file: Path) -> None:
        with patch("bim.commands.delete_note.delete_note.console") as mock_console:
            delete_single(zettel_file, quiet=True)
            mock_console.success.assert_not_called()

    def test_loud_prints_console(self, zettel_file: Path) -> None:
        with patch("bim.commands.delete_note.delete_note.console") as mock_console:
            delete_single(zettel_file)
            mock_console.success.assert_called_once()


class TestCommandDeleteNote:
    def test_force_deletes_without_confirm(self, zettel_file: Path) -> None:
        cmd = CommandDeleteNote(paths=[zettel_file], force=True)
        cmd.execute()
        assert not zettel_file.exists()

    def test_no_force_confirms(self, zettel_file: Path) -> None:
        with patch("bim.commands.delete_note.delete_note.console") as mock_console:
            mock_console.confirm.return_value = True
            cmd = CommandDeleteNote(paths=[zettel_file])
            cmd.execute()
            mock_console.confirm.assert_called_once()
            assert not zettel_file.exists()

    def test_no_force_declined(self, zettel_file: Path) -> None:
        with patch("bim.commands.delete_note.delete_note.console") as mock_console:
            mock_console.confirm.return_value = False
            cmd = CommandDeleteNote(paths=[zettel_file])
            cmd.execute()
            assert zettel_file.exists()

    def test_missing_file_reports_failure(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        with patch("bim.commands.delete_note.delete_note.console") as mock_console:
            cmd = CommandDeleteNote(paths=[missing], force=True)
            cmd.execute()
            mock_console.failure.assert_called_once()
