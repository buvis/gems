from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from fctracker.commands.transactions.transactions import CommandTransactions
from fctracker.settings import ForeignCurrencyConfig, LocalCurrencyConfig


def _make_deposit(date_str: str, amount: str, rate: str, symbol: str) -> MagicMock:
    """Build a mock Deposit transaction."""
    from fctracker.domain import Deposit

    d = MagicMock(spec=Deposit)
    d.date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    d.amount = Decimal(amount)
    d.rate = Decimal(rate)
    d.currency_symbol = symbol
    d.get_local_cost.return_value = Decimal(amount) * Decimal(rate)
    d.is_in_month.return_value = True
    return d


def _make_withdrawal(date_str: str, amount: str, rate: str, symbol: str, desc: str) -> MagicMock:
    """Build a mock Withdrawal transaction."""
    from fctracker.domain import Withdrawal

    w = MagicMock(spec=Withdrawal)
    w.date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    w.amount = Decimal(amount)
    w.rate = Decimal(rate)
    w.currency_symbol = symbol
    w.description = desc
    w.get_local_cost.return_value = Decimal(amount) * Decimal(rate)
    w.is_in_month.return_value = True
    return w


class TestCommandTransactions:
    def _make_cmd(
        self,
        account: str = "",
        currency: str = "",
        month: str = "",
    ) -> CommandTransactions:
        foreign = {
            "EUR": ForeignCurrencyConfig(symbol="E", precision=2),
            "USD": ForeignCurrencyConfig(symbol="$", precision=2),
        }
        local = LocalCurrencyConfig(code="CZK", symbol="Kc", precision=2)
        return CommandTransactions(
            foreign_currencies=foreign,
            local_currency=local,
            account=account,
            currency=currency,
            month=month,
        )

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_empty_accounts(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {}
        cmd = self._make_cmd()
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is True
        assert result.metadata["tables"] == []

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_deposit_transaction(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        deposit = _make_deposit("2024-03-15", "100", "25.50", "E")
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        def fill_transactions(reader_self=None):
            account_obj = mock_reader_cls.call_args[0][0]
            account_obj.transactions = [deposit]

        mock_reader_cls.return_value.get_transactions.side_effect = lambda: fill_transactions()

        # We need to mock Account so its transactions list is populated
        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            mock_account.transactions = [deposit]
            mock_account.__repr__ = lambda s: "Acme[EUR]"
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd()
            result = cmd.execute()

        assert result.success is True
        tables = result.metadata["tables"]
        assert len(tables) == 1
        rows = tables[0]["rows"]
        assert len(rows) == 1
        assert rows[0]["description"] == "Deposit"
        assert rows[0]["outflow"] == ""
        assert "Kc" in rows[0]["inflow"]

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_withdrawal_transaction(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        withdrawal = _make_withdrawal("2024-03-20", "50", "25.00", "E", "Amazon purchase")
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            mock_account.transactions = [withdrawal]
            mock_account.__repr__ = lambda s: "Acme[EUR]"
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd()
            result = cmd.execute()

        assert result.success is True
        tables = result.metadata["tables"]
        assert len(tables) == 1
        rows = tables[0]["rows"]
        assert len(rows) == 1
        assert rows[0]["description"] == "Amazon purchase"
        assert "Kc" in rows[0]["outflow"]
        assert rows[0]["inflow"] == ""

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_filter_by_account(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        deposit = _make_deposit("2024-03-15", "100", "25.50", "E")
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"], "Other": ["USD"]}

        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            mock_account.transactions = [deposit]
            mock_account.__str__ = lambda s: "Acme[EUR]"
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd(account="acme")
            result = cmd.execute()

        assert result.success is True
        tables = result.metadata["tables"]
        # Only Acme matched, not Other
        assert len(tables) == 1

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_filter_by_currency(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        deposit = _make_deposit("2024-03-15", "100", "25.50", "$")
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR", "USD"]}

        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            mock_account.transactions = [deposit]
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd(currency="usd")
            result = cmd.execute()

        assert result.success is True
        tables = result.metadata["tables"]
        assert len(tables) == 1

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_filter_by_month(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        march = _make_deposit("2024-03-15", "100", "25.50", "E")
        march.is_in_month.return_value = True
        april = _make_deposit("2024-04-01", "200", "26.00", "E")
        april.is_in_month.return_value = False

        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            mock_account.transactions = [march, april]
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd(month="2024-03")
            result = cmd.execute()

        assert result.success is True
        tables = result.metadata["tables"]
        assert len(tables) == 1
        rows = tables[0]["rows"]
        assert len(rows) == 1

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_no_transactions(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            mock_account.transactions = []
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd()
            result = cmd.execute()

        assert result.success is True
        tables = result.metadata["tables"]
        assert len(tables) == 1
        assert tables[0]["rows"] == []

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_mixed_deposits_and_withdrawals(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        deposit = _make_deposit("2024-03-15", "100", "25.50", "E")
        withdrawal = _make_withdrawal("2024-03-20", "50", "25.00", "E", "Groceries")
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            mock_account.transactions = [deposit, withdrawal]
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd()
            result = cmd.execute()

        assert result.success is True
        tables = result.metadata["tables"]
        rows = tables[0]["rows"]
        assert len(rows) == 2
        descs = [r["description"] for r in rows]
        assert "Deposit" in descs
        assert "Groceries" in descs

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_row_seq_descending(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        d1 = _make_deposit("2024-03-10", "50", "25.00", "E")
        d2 = _make_deposit("2024-03-15", "100", "25.50", "E")
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            # transactions are stored oldest-first, reversed in code
            mock_account.transactions = [d1, d2]
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd()
            result = cmd.execute()

        rows = result.metadata["tables"][0]["rows"]
        assert rows[0]["seq"] == "2"
        assert rows[1]["seq"] == "1"

    @patch("fctracker.commands.transactions.transactions.TransactionsReader")
    @patch("fctracker.commands.transactions.transactions.TransactionsDirScanner")
    def test_rate_format(self, mock_scanner_cls: MagicMock, mock_reader_cls: MagicMock) -> None:
        deposit = _make_deposit("2024-03-15", "100", "25.50", "E")
        mock_scanner_cls.return_value.accounts = {"Acme": ["EUR"]}

        with patch("fctracker.commands.transactions.transactions.Account") as mock_account_cls:
            mock_account = MagicMock()
            mock_account.transactions = [deposit]
            mock_account_cls.return_value = mock_account

            cmd = self._make_cmd()
            result = cmd.execute()

        row = result.metadata["tables"][0]["rows"][0]
        # precision is 2, so rate precision is 4 (2*2)
        assert "25.5000 Kc/E" in row["rate"]
