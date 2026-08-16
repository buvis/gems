from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fctracker.adapters.transactions.transactions_reader import TransactionsReader


class TestTransactionsReader:
    def test_reads_deposits_and_withdrawals(self, tmp_path: Path) -> None:
        csv_content = "date,amount,rate,description\n2024-01-20,-50.00,,Amazon purchase\n2024-01-15,100.00,25.50,\n"
        account = MagicMock()
        account.name = "acme"
        account.currency = "eur"

        csv_path = tmp_path / "acme" / "eur.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)
            reader.get_transactions()

        assert account.deposit.call_count == 1
        assert account.withdraw.call_count == 1

        # Check deposit call
        dep_call = account.deposit.call_args
        assert dep_call.kwargs["amount"] == Decimal("100.00")
        assert dep_call.kwargs["rate"] == Decimal("25.50")

        # Check withdraw call
        wd_call = account.withdraw.call_args
        assert wd_call.kwargs["amount"] == Decimal("50.00")
        assert wd_call.kwargs["description"] == "Amazon purchase"

    def test_processes_rows_in_reverse_order(self, tmp_path: Path) -> None:
        csv_content = "date,amount,rate,description\n2024-02-01,20.00,26.00,\n2024-01-01,10.00,25.00,\n"
        account = MagicMock()
        account.name = "bank"
        account.currency = "usd"

        csv_path = tmp_path / "bank" / "usd.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)
            reader.get_transactions()

        # Rows reversed: 2024-01-01 (last in file) processed first, then 2024-02-01
        calls = account.deposit.call_args_list
        assert calls[0].kwargs["amount"] == Decimal("10.00")
        assert calls[1].kwargs["amount"] == Decimal("20.00")

    def test_file_path_constructed_correctly(self, tmp_path: Path) -> None:
        account = MagicMock()
        account.name = "Acme"
        account.currency = "EUR"

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)

        assert reader.file_path == tmp_path / "acme" / "eur.csv"

    def test_accepts_non_decreasing_dates_including_equal_dates(self, tmp_path: Path) -> None:
        # File is newest-first; after reversal the oldest-first order is
        # 2024-01-10, 2024-01-10, 2024-01-20 -- non-decreasing (equal dates
        # allowed), so no error should be raised and every row is processed.
        csv_content = (
            "date,amount,rate,description\n2024-01-20,20.00,25.00,\n2024-01-10,10.00,25.00,\n2024-01-10,15.00,25.00,\n"
        )
        account = MagicMock()
        account.name = "acme"
        account.currency = "eur"

        csv_path = tmp_path / "acme" / "eur.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)
            reader.get_transactions()

        assert account.deposit.call_count == 3

    def test_rejects_non_monotonic_date_order(self, tmp_path: Path) -> None:
        # File claims to be newest-first, but data row 2 (2024-01-20) is
        # newer than data row 1 (2024-01-10) -- row 2 is the offender: it
        # should be no later than row 1 but isn't. After reversal the
        # in-memory order is 2024-01-05, 2024-01-20, 2024-01-10, so the raw
        # reversed-list index trips at 2 (dates[2] < dates[1]) -- the same
        # number the corrected message reports, by coincidence, for this
        # symmetric 3-row fixture. The mapping bug only becomes visible when
        # index and data row diverge, which is what the 4-row fixture in
        # test_order_violation_names_offending_row_and_csv exists to catch.
        csv_content = (
            "date,amount,rate,description\n2024-01-10,10.00,25.00,\n2024-01-20,20.00,25.00,\n2024-01-05,30.00,25.00,\n"
        )
        account = MagicMock()
        account.name = "acme"
        account.currency = "eur"

        csv_path = tmp_path / "acme" / "eur.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)

            with pytest.raises(ValueError, match="transactions must be newest-first; data row 2 breaks order"):
                reader.get_transactions()

        assert account.deposit.call_count == 0
        assert account.withdraw.call_count == 0

    def test_order_violation_names_offending_row_and_csv(self, tmp_path: Path) -> None:
        # File (newest-first expected), data rows as the user counts them:
        #   row 1: 2024-04-01
        #   row 2: 2024-03-01
        #   row 3: 2024-01-01
        #   row 4: 2024-02-01  <- offender: newer than row 3, so it should be
        #                         no later than row 3 but isn't.
        # The raw reversed-list index where the naive check trips is 1 (or a
        # simple len-based offset of it would be 4), far enough from the
        # correct data row 4 that an off-by-one or off-by-a-constant fix
        # cannot pass this fixture by accident.
        csv_content = (
            "date,amount,rate,description\n"
            "2024-04-01,10.00,25.00,\n"
            "2024-03-01,10.00,25.00,\n"
            "2024-01-01,10.00,25.00,\n"
            "2024-02-01,10.00,25.00,\n"
        )
        account = MagicMock()
        account.name = "acme"
        account.currency = "eur"

        csv_path = tmp_path / "acme" / "eur.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)

            with pytest.raises(ValueError) as exc_info:
                reader.get_transactions()

        message = str(exc_info.value)
        # A. reports the DATA row number (header excluded, first data row = 1),
        #    and states the numbering convention explicitly ("data row").
        assert "data row 4" in message
        # C. the newest-first instruction must survive the row-number fix.
        assert "newest-first" in message
        # B. identifies which CSV: account.name and self.file_path both
        #    contain "acme" for this fixture, so either satisfies this.
        assert "acme" in message
        # D. fail-before-mutate: no transaction applied on an order violation.
        assert account.deposit.call_count == 0
        assert account.withdraw.call_count == 0

    def test_malformed_amount_cell_names_offending_value(self, tmp_path: Path) -> None:
        csv_content = "date,amount,rate,description\n2024-01-15,abc,25.50,\n"
        account = MagicMock()
        account.name = "acme"
        account.currency = "eur"

        csv_path = tmp_path / "acme" / "eur.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)

            with pytest.raises(Exception) as exc_info:
                reader.get_transactions()

        message = str(exc_info.value)
        assert "abc" in message
        assert "<class '" not in message
        assert "zero" not in message.lower()

    def test_zero_amount_withdrawal_indicates_zero_amount(self, tmp_path: Path) -> None:
        from fctracker.domain.account import Account

        csv_content = "date,amount,rate,description\n2024-01-15,0.00,,\n"
        account = Account(
            name="acme",
            currency="eur",
            precision=2,
            symbol="E",
            local_precision=2,
            local_symbol="Kc",
        )

        csv_path = tmp_path / "acme" / "eur.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)

            with pytest.raises(Exception) as exc_info:
                reader.get_transactions()

        message = str(exc_info.value)
        assert "zero" in message.lower()
        assert "<class '" not in message

    def test_malformed_date_cell_names_value_and_is_not_order_violation(self, tmp_path: Path) -> None:
        csv_content = "date,amount,rate,description\n2024-13-99,10.00,25.00,\n"
        account = MagicMock()
        account.name = "acme"
        account.currency = "eur"

        csv_path = tmp_path / "acme" / "eur.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)

            with pytest.raises(Exception) as exc_info:
                reader.get_transactions()

        message = str(exc_info.value)
        assert "2024-13-99" in message
        assert "newest-first" not in message
