from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from bim.commands.format_note.format_note import CommandFormatNote, format_single


@pytest.fixture
def zettel_file(tmp_path: Path, minimal_zettel: str) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text(minimal_zettel, encoding="utf-8")
    return p


class TestFormatSingle:
    def test_returns_formatted_content(self, zettel_file: Path, format_note_mocks) -> None:
        result = format_single(zettel_file)

        assert result == "formatted content"

    def test_in_place_writes_file(self, zettel_file: Path, format_note_mocks) -> None:
        format_single(zettel_file, in_place=True, quiet=True)

        assert zettel_file.read_text(encoding="utf-8") == "formatted content"

    def test_quiet_suppresses_console(self, zettel_file: Path, format_note_mocks) -> None:
        with (
            patch("bim.commands.format_note.format_note.console") as mock_console,
        ):
            format_single(zettel_file, in_place=True, quiet=True)

            mock_console.success.assert_not_called()

    def test_loud_prints_console(self, zettel_file: Path, format_note_mocks) -> None:
        with (
            patch("bim.commands.format_note.format_note.console") as mock_console,
        ):
            format_single(zettel_file, in_place=True)

            mock_console.success.assert_called_once()


class TestCommandFormatNote:
    def test_missing_file_reports_failure(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.md"
        with patch("bim.commands.format_note.format_note.console") as mock_console:
            cmd = CommandFormatNote(paths=[missing])
            cmd.execute()
            mock_console.failure.assert_called_once()

    def test_writes_to_output_file(self, zettel_file: Path, tmp_path: Path) -> None:
        output_path = tmp_path / "formatted.md"
        with (
            patch("bim.commands.format_note.format_note.format_single") as mock_format,
            patch("bim.commands.format_note.format_note.console") as mock_console,
        ):
            mock_format.return_value = "formatted"

            cmd = CommandFormatNote(paths=[zettel_file], path_output=output_path)
            cmd.execute()

            assert output_path.read_text(encoding="utf-8") == "formatted"
            mock_console.success.assert_called_once_with(
                f"Formatted note was written to {output_path}",
            )

    def test_diff_calls_side_by_side(self, zettel_file: Path) -> None:
        with (
            patch("bim.commands.format_note.format_note.format_single") as mock_format,
            patch("bim.commands.format_note.format_note.console") as mock_console,
        ):
            original = zettel_file.read_text()
            mock_format.return_value = "formatted"

            cmd = CommandFormatNote(paths=[zettel_file], is_diff_requested=True)
            cmd.execute()

            mock_console.print_side_by_side.assert_called_once_with(
                "Original",
                original,
                "Formatted",
                "formatted",
                mode_left="raw",
                mode_right="markdown_with_frontmatter",
            )

    def test_highlight_calls_console_print(self, zettel_file: Path) -> None:
        with (
            patch("bim.commands.format_note.format_note.format_single") as mock_format,
            patch("bim.commands.format_note.format_note.console") as mock_console,
        ):
            mock_format.return_value = "formatted"

            cmd = CommandFormatNote(paths=[zettel_file], is_highlighting_requested=True)
            cmd.execute()

            mock_console.print.assert_called_once_with(
                "formatted",
                mode="markdown_with_frontmatter",
            )

    def test_raw_calls_console_print(self, zettel_file: Path) -> None:
        with (
            patch("bim.commands.format_note.format_note.format_single") as mock_format,
            patch("bim.commands.format_note.format_note.console") as mock_console,
        ):
            mock_format.return_value = "formatted"

            cmd = CommandFormatNote(paths=[zettel_file])
            cmd.execute()

            mock_console.print.assert_called_once_with(
                "formatted",
                mode="raw",
            )

    def test_batch_formats_all(self, tmp_path: Path, minimal_zettel: str) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text(minimal_zettel, encoding="utf-8")
        b.write_text(minimal_zettel, encoding="utf-8")

        with patch("bim.commands.format_note.format_note.format_single") as mock_format:
            mock_format.return_value = "formatted"
            cmd = CommandFormatNote(paths=[a, b])
            cmd.execute()
            assert mock_format.call_count == 2
            mock_format.assert_any_call(a, in_place=True)
            mock_format.assert_any_call(b, in_place=True)

    def test_batch_skips_missing(self, tmp_path: Path, minimal_zettel: str) -> None:
        exists = tmp_path / "exists.md"
        exists.write_text(minimal_zettel, encoding="utf-8")
        missing = tmp_path / "missing.md"

        with (
            patch("bim.commands.format_note.format_note.format_single") as mock_format,
            patch("bim.commands.format_note.format_note.console") as mock_console,
        ):
            mock_format.return_value = "formatted"
            cmd = CommandFormatNote(paths=[missing, exists])
            cmd.execute()
            mock_console.failure.assert_called_once()
            mock_format.assert_called_once_with(exists, in_place=True)
