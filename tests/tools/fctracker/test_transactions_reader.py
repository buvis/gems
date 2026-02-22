from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from fctracker.adapters.transactions.transactions_reader import TransactionsReader


class TestTransactionsReader:
    def test_reads_deposits_and_withdrawals(self, tmp_path: Path) -> None:
        csv_content = "date,amount,rate,description\n2024-01-15,100.00,25.50,\n2024-01-20,-50.00,,Amazon purchase\n"
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
        csv_content = "date,amount,rate,description\n2024-01-01,10.00,25.00,\n2024-02-01,20.00,26.00,\n"
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

        # Rows reversed: 2024-02-01 processed first, then 2024-01-01
        calls = account.deposit.call_args_list
        assert calls[0].kwargs["amount"] == Decimal("20.00")
        assert calls[1].kwargs["amount"] == Decimal("10.00")

    def test_file_path_constructed_correctly(self, tmp_path: Path) -> None:
        account = MagicMock()
        account.name = "Acme"
        account.currency = "EUR"

        with patch("fctracker.adapters.transactions.transactions_reader.cfg") as mock_cfg:
            mock_cfg.transactions_dir = tmp_path
            reader = TransactionsReader(account)

        assert reader.file_path == tmp_path / "acme" / "eur.csv"
