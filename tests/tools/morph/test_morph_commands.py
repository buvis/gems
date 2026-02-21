from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from morph.cli import cli


class TestMorphCommands:
    @patch("morph.commands.html2md.html2md.CommandHtml2Md")
    def test_html2md_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Converted 5 files")
        runner = CliRunner()
        result = runner.invoke(cli, ["html2md", str(tmp_path)])
        assert result.exit_code == 0

    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_deblank_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Processed 1 file")
        runner = CliRunner()
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert result.exit_code == 0
