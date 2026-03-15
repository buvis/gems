from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from fctracker.cli import cli


class TestFctrackerBalanceExtra:
    @patch("fctracker.commands.balance.balance.CommandBalance")
    def test_balance_with_accounts(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_account = MagicMock()
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="ok",
            metadata={"accounts": [mock_account]},
        )
        result = runner.invoke(cli, ["balance"])
        assert result.exit_code == 0


class TestFctrackerTransactionsExtra:
    @patch("fctracker.commands.transactions.transactions.CommandTransactions")
    def test_transactions_with_table_data(self, mock_cmd_cls: MagicMock, runner) -> None:
        table_data = {
            "title": "USD Transactions",
            "rows": [
                {
                    "seq": "1",
                    "date": "2024-01-15",
                    "description": "Transfer",
                    "amount": "100.00",
                    "rate": "23.50",
                    "outflow": "2350.00",
                    "inflow": "",
                },
            ],
        }
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="ok",
            metadata={"tables": [table_data]},
        )
        result = runner.invoke(cli, ["transactions"])
        assert result.exit_code == 0

    @patch("fctracker.commands.transactions.transactions.CommandTransactions")
    def test_transactions_execute_file_not_found(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=False, error="no transactions dir"
        )
        result = runner.invoke(cli, ["transactions"])
        assert result.exit_code != 0
        assert "no transactions dir" in result.output
