from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from fctracker.commands.balance.balance import CommandBalance
from fctracker.settings import ForeignCurrencyConfig, LocalCurrencyConfig


class TestCommandBalance:
    def _make_cmd(self) -> CommandBalance:
        foreign = {
            "EUR": ForeignCurrencyConfig(symbol="E", precision=2),
            "USD": ForeignCurrencyConfig(symbol="$", precision=2),
        }
        local = LocalCurrencyConfig(code="CZK", symbol="Kc", precision=2)
        return CommandBalance(
            foreign_currencies=foreign,
            local_currency=local,
        )

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_empty_accounts(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {}
        cmd = self._make_cmd()
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is True
        assert result.metadata["accounts"] == []

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_single_account(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        cmd = self._make_cmd()
        result = cmd.execute()

        assert result.success is True
        assert len(result.metadata["accounts"]) == 1
        mock_reader_cls.assert_called_once()
        mock_reader_cls.return_value.get_transactions.assert_called_once()

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_multiple_currencies(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR", "USD"]}

        cmd = self._make_cmd()
        result = cmd.execute()

        assert result.success is True
        assert len(result.metadata["accounts"]) == 2
        assert mock_reader_cls.call_count == 2
        assert mock_reader_cls.return_value.get_transactions.call_count == 2

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_multiple_accounts(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {
            "Acme": ["EUR"],
            "Other": ["USD"],
        }

        cmd = self._make_cmd()
        result = cmd.execute()

        assert result.success is True
        assert len(result.metadata["accounts"]) == 2

    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_scanner_file_not_found(self, mock_scanner_cls: MagicMock) -> None:
        mock_scanner_cls.side_effect = FileNotFoundError("transactions dir missing")
        cmd = self._make_cmd()
        result = cmd.execute()

        assert result.success is False
        assert "transactions dir missing" in result.error

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_reader_file_not_found(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}
        mock_reader_cls.return_value.get_transactions.side_effect = FileNotFoundError("data file missing")

        cmd = self._make_cmd()
        result = cmd.execute()

        assert result.success is False
        assert "data file missing" in result.error
