from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from hello_world.cli import cli


class TestHelloWorldCommands:
    @patch("hello_world.commands.diagnostics.diagnostics.CommandDiagnostics")
    def test_diag(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Python 3.12")
        result = runner.invoke(cli, ["--diag"])
        assert result.exit_code == 0

    @patch("hello_world.commands.list_fonts.list_fonts.CommandListFonts")
    @patch("hello_world.cli.pyfiglet", create=True)
    def test_list_fonts(self, mock_pyfiglet: MagicMock, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="doom\nbanner")
        result = runner.invoke(cli, ["--list-fonts"])
        assert result.exit_code == 0

    @patch("hello_world.commands.print_figlet.print_figlet.CommandPrintFiglet")
    def test_text(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="styled text")
        result = runner.invoke(cli, ["hello"])
        assert result.exit_code == 0
