from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from fctracker.cli import cli


class TestFctrackerCommands:
    @patch("fctracker.commands.balance.balance.CommandBalance")
    def test_balance_success(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="ok",
            metadata={"accounts": []},
        )
        result = runner.invoke(cli, ["balance"])
        assert result.exit_code == 0

    @patch("fctracker.commands.balance.balance.CommandBalance")
    def test_balance_file_not_found(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=False, error="no dir"
        )
        result = runner.invoke(cli, ["balance"])
        assert result.exit_code != 0
        assert "no dir" in result.output

    @patch("fctracker.commands.transactions.transactions.CommandTransactions")
    def test_transactions_success(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="ok",
            metadata={"tables": []},
        )
        result = runner.invoke(cli, ["transactions"])
        assert result.exit_code == 0

    @patch("fctracker.commands.transactions.transactions.CommandTransactions")
    def test_transactions_with_filters(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="ok",
            metadata={"tables": []},
        )
        result = runner.invoke(cli, ["transactions", "-a", "acme", "-c", "USD", "-m", "2024-01"])
        assert result.exit_code == 0

    @patch("fctracker.commands.transactions.transactions.CommandTransactions")
    def test_transactions_file_not_found(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=False, error="missing"
        )
        result = runner.invoke(cli, ["transactions"])
        assert result.exit_code != 0
        assert "missing" in result.output
