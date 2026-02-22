from __future__ import annotations

from pathlib import Path
from unittest.mock import PropertyMock, patch

from fctracker.adapters.transactions.transactions_dir_scanner import TransactionsDirScanner


class TestTransactionsDirScanner:
    def test_discovers_accounts_and_csv_files(self, tmp_path: Path) -> None:
        acme = tmp_path / "acme"
        acme.mkdir()
        (acme / "USD.csv").write_text("header")
        (acme / "EUR.csv").write_text("header")
        (acme / "notes.txt").write_text("skip")

        beta = tmp_path / "beta"
        beta.mkdir()
        (beta / "GBP.csv").write_text("header")

        with patch("fctracker.adapters.transactions.transactions_dir_scanner.cfg") as mock_cfg:
            type(mock_cfg).transactions_dir = PropertyMock(return_value=tmp_path)
            scanner = TransactionsDirScanner()

        assert "Acme" in scanner.accounts
        assert "Beta" in scanner.accounts
        assert sorted(scanner.accounts["Acme"]) == ["EUR", "USD"]
        assert scanner.accounts["Beta"] == ["GBP"]

    def test_empty_account_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()

        with patch("fctracker.adapters.transactions.transactions_dir_scanner.cfg") as mock_cfg:
            type(mock_cfg).transactions_dir = PropertyMock(return_value=tmp_path)
            scanner = TransactionsDirScanner()

        assert scanner.accounts["Empty"] == []

    def test_ignores_subdirectories(self, tmp_path: Path) -> None:
        acct = tmp_path / "acct"
        acct.mkdir()
        subdir = acct / "subdir"
        subdir.mkdir()

        with patch("fctracker.adapters.transactions.transactions_dir_scanner.cfg") as mock_cfg:
            type(mock_cfg).transactions_dir = PropertyMock(return_value=tmp_path)
            scanner = TransactionsDirScanner()

        assert scanner.accounts["Acct"] == []
