from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from fctracker.cli import cli


class TestFctrackerCommands:
    @patch("fctracker.commands.balance.balance.CommandBalance")
    def test_balance_success(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="ok",
            metadata={"accounts": []},
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["balance"])
        assert result.exit_code == 0

    @patch("fctracker.commands.balance.balance.CommandBalance")
    def test_balance_file_not_found(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.side_effect = FileNotFoundError("no dir")
        runner = CliRunner()
        result = runner.invoke(cli, ["balance"])
        assert result.exit_code != 0 or "no dir" in result.output

    @patch("fctracker.commands.transactions.transactions.CommandTransactions")
    def test_transactions_success(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="ok",
            metadata={"tables": []},
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["transactions"])
        assert result.exit_code == 0

    @patch("fctracker.commands.transactions.transactions.CommandTransactions")
    def test_transactions_with_filters(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="ok",
            metadata={"tables": []},
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["transactions", "-a", "acme", "-c", "USD", "-m", "2024-01"])
        assert result.exit_code == 0

    @patch("fctracker.commands.transactions.transactions.CommandTransactions")
    def test_transactions_file_not_found(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.side_effect = FileNotFoundError("missing")
        runner = CliRunner()
        result = runner.invoke(cli, ["transactions"])
        assert result.exit_code != 0 or "missing" in result.output
