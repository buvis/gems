from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bim.commands.format_note.format_note import CommandFormatNote
from bim.params.format_note import FormatNoteParams


@pytest.fixture
def zettel_file(tmp_path: Path, minimal_zettel: str) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text(minimal_zettel, encoding="utf-8")
    return p


@pytest.fixture
def format_note_dependencies():
    repo = MagicMock()
    formatter = MagicMock()
    note = MagicMock()
    with (
        patch("bim.commands.format_note.format_note.ReadZettelUseCase") as mock_reader_cls,
        patch("bim.commands.format_note.format_note.PrintZettelUseCase") as mock_printer_cls,
    ):
        reader = mock_reader_cls.return_value
        reader.execute.return_value = note
        printer = mock_printer_cls.return_value
        printer.execute.return_value = "formatted content"
        yield {
            "repo": repo,
            "formatter": formatter,
            "reader": reader,
            "printer": printer,
            "mock_reader_cls": mock_reader_cls,
            "mock_printer_cls": mock_printer_cls,
        }


class TestCommandFormatNote:
    def test_missing_file_reports_failure(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.md"
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[missing]),
            repo=MagicMock(),
            formatter=MagicMock(),
        )
        result = cmd.execute()
        assert result.success is False
        assert result.error == f"{missing} doesn't exist"

    def test_writes_to_output_file(
        self,
        zettel_file: Path,
        tmp_path: Path,
        format_note_dependencies,
    ) -> None:
        output_path = tmp_path / "formatted.md"
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[zettel_file], path_output=output_path),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()

        assert result.success is True
        assert result.metadata["written_to"] == str(output_path)
        assert output_path.read_text(encoding="utf-8") == "formatted content"

    def test_batch_formats_all(
        self,
        tmp_path: Path,
        minimal_zettel: str,
        format_note_dependencies,
    ) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text(minimal_zettel, encoding="utf-8")
        b.write_text(minimal_zettel, encoding="utf-8")

        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[a, b]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()
        assert result.success is True
        assert result.metadata["formatted_count"] == 2
        assert a.read_text(encoding="utf-8") == "formatted content"
        assert b.read_text(encoding="utf-8") == "formatted content"

    def test_batch_skips_missing(
        self,
        tmp_path: Path,
        minimal_zettel: str,
        format_note_dependencies,
    ) -> None:
        exists = tmp_path / "exists.md"
        exists.write_text(minimal_zettel, encoding="utf-8")
        missing = tmp_path / "missing.md"

        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[missing, exists]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()
        assert result.success is True
        assert result.metadata["formatted_count"] == 1
        assert result.warnings == [f"{missing} doesn't exist"]
        assert exists.read_text(encoding="utf-8") == "formatted content"

    def test_single_returns_content(
        self,
        zettel_file: Path,
        format_note_dependencies,
    ) -> None:
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[zettel_file]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()

        assert result.success is True
        assert result.output == "formatted content"

    def test_single_includes_original(
        self,
        zettel_file: Path,
        format_note_dependencies,
    ) -> None:
        original = zettel_file.read_text(encoding="utf-8")
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[zettel_file]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()

        assert result.success is True
        assert result.metadata["original"] == original
