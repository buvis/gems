from __future__ import annotations

import queue
from decimal import Decimal, InvalidOperation
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.result import CommandResult
from fctracker.commands.balance.balance import CommandBalance
from fctracker.settings import ForeignCurrencyConfig, LocalCurrencyConfig


def _has_meaningful_cause(error: str) -> bool:
    """True only if the text after error's last colon has >=3 alphabetic chars.

    Guards against a blank cause such as
    "error processing transactions for account 'Acme': " (trailing space,
    no message) - the exact defect that shipped in the sibling command.
    """
    tail = error.rsplit(":", 1)[-1].strip(" '\"")
    return sum(ch.isalpha() for ch in tail) >= 3


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

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_reader_order_violation(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}
        mock_reader_cls.return_value.get_transactions.side_effect = ValueError(
            "transactions must be newest-first; row 3 breaks order"
        )

        cmd = self._make_cmd()
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is False
        assert result.error
        assert "Acme" in result.error
        assert _has_meaningful_cause(result.error)
        assert "<class '" not in result.error

    def test_meaningful_cause_guard_rejects_blank_cause(self) -> None:
        # Direct proof the guard catches the exact blank-cause defect that
        # shipped in the sibling command: a trailing colon with no message.
        assert _has_meaningful_cause("error processing transactions for account 'Acme': ") is False

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_reader_overdraft(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}
        mock_reader_cls.return_value.get_transactions.side_effect = queue.Empty()

        cmd = self._make_cmd()
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is False
        assert result.error
        assert "Acme" in result.error
        assert _has_meaningful_cause(result.error)
        assert "<class '" not in result.error

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_reader_malformed_amount_cell(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}
        with pytest.raises(InvalidOperation) as exc_info:
            Decimal("abc")
        mock_reader_cls.return_value.get_transactions.side_effect = exc_info.value

        cmd = self._make_cmd()
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is False
        assert result.error
        assert "Acme" in result.error
        assert _has_meaningful_cause(result.error)
        assert "<class '" not in result.error

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_reader_zero_amount_division(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}
        with pytest.raises(InvalidOperation) as exc_info:
            Decimal("0") / Decimal("0")
        mock_reader_cls.return_value.get_transactions.side_effect = exc_info.value

        cmd = self._make_cmd()
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is False
        assert result.error
        assert "Acme" in result.error
        assert _has_meaningful_cause(result.error)
        assert "<class '" not in result.error

    @patch("fctracker.commands.balance.balance.TransactionsReader")
    @patch("fctracker.commands.balance.balance.TransactionsDirScanner")
    def test_zero_amount_division_error_differs_from_malformed_amount_error(
        self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock
    ) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        with pytest.raises(InvalidOperation) as conversion_exc_info:
            Decimal("abc")
        mock_reader_cls.return_value.get_transactions.side_effect = conversion_exc_info.value
        malformed_result = self._make_cmd().execute()

        with pytest.raises(InvalidOperation) as division_exc_info:
            Decimal("0") / Decimal("0")
        mock_reader_cls.return_value.get_transactions.side_effect = division_exc_info.value
        zero_result = self._make_cmd().execute()

        assert malformed_result.success is False
        assert zero_result.success is False
        assert malformed_result.error != zero_result.error
