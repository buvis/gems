from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from morph.cli import cli


class TestHtml2MdExitCode:
    @patch("morph.commands.html2md.html2md.CommandHtml2Md")
    def test_exits_nonzero_when_result_fails(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="conversion failed")
        result = runner.invoke(cli, ["html2md", str(tmp_path)])
        assert result.exit_code != 0
        assert "conversion failed" in result.output

    @patch("morph.commands.html2md.html2md.CommandHtml2Md")
    def test_exits_zero_when_result_succeeds(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Converted 3 files")
        result = runner.invoke(cli, ["html2md", str(tmp_path)])
        assert result.exit_code == 0


class TestDeblankExitCode:
    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_exits_nonzero_when_result_fails(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="deblank failed")
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert result.exit_code != 0
        assert "deblank failed" in result.output

    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_exits_zero_when_result_succeeds(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Removed 1 blank page")
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert result.exit_code == 0


class TestPdf2PngExitCode:
    @patch("morph.commands.pdf2png.pdf2png.CommandPdf2Png")
    def test_exits_nonzero_when_result_fails(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="render failed")
        result = runner.invoke(cli, ["pdf2png", str(pdf)])
        assert result.exit_code != 0
        assert "render failed" in result.output

    @patch("morph.commands.pdf2png.pdf2png.CommandPdf2Png")
    def test_exits_zero_when_result_succeeds(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Wrote stacked PNG")
        result = runner.invoke(cli, ["pdf2png", str(pdf)])
        assert result.exit_code == 0
