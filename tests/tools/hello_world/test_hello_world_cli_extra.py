from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from hello_world.cli import cli


class TestHelloWorldCliExtra:
    @patch("hello_world.commands.diagnostics.diagnostics.CommandDiagnostics")
    def test_diag_no_output(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["--diag"])
        assert result.exit_code == 0

    def test_import_error(self, runner) -> None:
        mod_key = "pyfiglet"
        saved = sys.modules.pop(mod_key, None)
        try:
            with patch.dict(sys.modules, {mod_key: None}):
                result = runner.invoke(cli, [])
                assert "hello-world" in result.output
        finally:
            if saved is not None:
                sys.modules[mod_key] = saved

    @patch("hello_world.commands.print_figlet.print_figlet.CommandPrintFiglet")
    def test_random_font(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="styled")
        result = runner.invoke(cli, ["--random-font", "hello"])
        assert result.exit_code == 0

    @patch("hello_world.commands.print_figlet.print_figlet.CommandPrintFiglet")
    def test_invalid_font_falls_back(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="styled")
        result = runner.invoke(cli, ["--font", "nonexistent_font_xyz", "hello"])
        assert result.exit_code == 0

    @patch("hello_world.commands.print_figlet.print_figlet.CommandPrintFiglet")
    def test_text_no_output(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["hello"])
        assert result.exit_code == 0
