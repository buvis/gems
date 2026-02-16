from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from bim.commands.show_note.show_note import CommandShowNote, show_single


@pytest.fixture
def zettel_file(tmp_path: Path, minimal_zettel: str) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text(minimal_zettel, encoding="utf-8")
    return p


class TestShowSingle:
    def test_returns_formatted_content(self, zettel_file: Path) -> None:
        result = show_single(zettel_file, quiet=True)
        assert "title: Original Title" in result
        assert "Some body text." in result

    def test_quiet_suppresses_console(self, zettel_file: Path) -> None:
        with patch("bim.commands.show_note.show_note.console") as mock_console:
            show_single(zettel_file, quiet=True)
            mock_console.print.assert_not_called()

    def test_loud_prints_console(self, zettel_file: Path) -> None:
        with patch("bim.commands.show_note.show_note.console") as mock_console:
            show_single(zettel_file)
            mock_console.print.assert_called_once()


class TestCommandShowNote:
    def test_execute_calls_show_single(self, zettel_file: Path) -> None:
        with patch("bim.commands.show_note.show_note.show_single") as mock:
            cmd = CommandShowNote(paths=[zettel_file])
            cmd.execute()
            mock.assert_called_once_with(zettel_file)
