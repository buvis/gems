from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from readerctl.cli import cli


class TestReaderctlCommands:
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_login_success(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Logged in")
        runner = CliRunner()
        result = runner.invoke(cli, ["login"])
        assert result.exit_code == 0

    @patch("readerctl.commands.login.login.CommandLogin")
    def test_login_failure(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="invalid token")
        runner = CliRunner()
        result = runner.invoke(cli, ["login"])
        assert result.exit_code == 0  # CLI prints failure but doesn't sys.exit

    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_url_success(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock) -> None:
        mock_login_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="Logged in",
            metadata={"token": "tok123"},
        )
        mock_add_cls.return_value.execute.return_value = CommandResult(success=True, output="Added")
        runner = CliRunner()
        result = runner.invoke(cli, ["add", "--url", "https://example.com"])
        assert result.exit_code == 0

    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_no_token_panics(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock) -> None:
        mock_login_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="Logged in",
            metadata={},  # no token
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["add", "--url", "https://example.com"])
        assert result.exit_code != 0 or "Not logged in" in result.output
