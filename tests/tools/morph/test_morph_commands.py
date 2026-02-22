from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult, FatalError
from click.testing import CliRunner
from morph.cli import cli


class TestMorphHtml2MdCommand:
    @patch("morph.commands.html2md.html2md.CommandHtml2Md")
    def test_html2md_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Converted 5 files")
        runner = CliRunner()
        result = runner.invoke(cli, ["html2md", str(tmp_path)])
        assert result.exit_code == 0
        assert "Converted 5 files" in result.output

    @patch("morph.commands.html2md.html2md.CommandHtml2Md")
    def test_html2md_success_no_output(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        runner = CliRunner()
        result = runner.invoke(cli, ["html2md", str(tmp_path)])
        assert result.exit_code == 0

    @patch("morph.commands.html2md.html2md.CommandHtml2Md")
    def test_html2md_failure(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="bad input")
        runner = CliRunner()
        result = runner.invoke(cli, ["html2md", str(tmp_path)])
        assert result.exit_code == 0

    @patch("morph.commands.html2md.html2md.CommandHtml2Md")
    def test_html2md_failure_no_error_message(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["html2md", str(tmp_path)])
        assert result.exit_code == 0

    @patch("morph.commands.html2md.html2md.CommandHtml2Md")
    def test_html2md_with_warnings(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Converted 1 file(s)", warnings=["Failed to convert bad.html: denied"]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["html2md", str(tmp_path)])
        assert result.exit_code == 0


class TestMorphDeblanCommand:
    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_deblank_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Processed 1 file")
        runner = CliRunner()
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert result.exit_code == 0
        assert "Processed 1 file" in result.output

    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_deblank_success_no_output(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        runner = CliRunner()
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert result.exit_code == 0

    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_deblank_failure(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="pdftk failed")
        runner = CliRunner()
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert result.exit_code == 0

    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_deblank_failure_no_error_message(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert result.exit_code == 0

    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_deblank_with_warnings(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Processed 1 file", warnings=["skipped blank.pdf"]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert result.exit_code == 0

    @patch("morph.commands.deblank.deblank.CommandDeblank", side_effect=FatalError("Missing tools"))
    def test_deblank_fatal_error(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        runner = CliRunner()
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert "Missing tools" in result.output
