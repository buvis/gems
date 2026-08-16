from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fctracker.adapters.config.config import cfg
from fctracker.domain.account import Account


class TransactionsReader:
    REQUIRED_COLUMNS = ("date", "amount", "rate", "description")
    REQUIRED_ROW_VALUES = ("date", "amount", "rate")

    def __init__(self, account: Account) -> None:
        self.file_path = Path(
            cfg.transactions_dir,
            account.name.lower(),
            f"{account.currency.lower()}.csv",
        )
        self.account = account

    def _read_rows(self) -> tuple[list[dict[str, str]], list[str]]:
        try:
            with open(self.file_path, encoding="utf-8-sig", newline="") as csvfile:
                reader = csv.DictReader(csvfile, skipinitialspace=True)

                rows: list[dict[str, str]] = []

                for row in reader:
                    rows.insert(0, row)

                return rows, list(reader.fieldnames or [])
        except UnicodeDecodeError:
            raise ValueError(f"{self.file_path}: file is not valid UTF-8") from None

    def _validate_columns(self, fieldnames: list[str]) -> None:
        for column in self.REQUIRED_COLUMNS:
            if column not in fieldnames:
                raise ValueError(f"{self.file_path}: missing required column '{column}'")

    def _validate_rows(self, rows: list[dict[str, str]]) -> None:
        for index, row in enumerate(rows):
            for column in self.REQUIRED_ROW_VALUES:
                if row[column] is None:
                    data_row = len(rows) - index
                    raise ValueError(f"{self.file_path}: row {data_row} is missing a value for '{column}'")

    def get_transactions(self) -> None:
        rows, fieldnames = self._read_rows()
        self._validate_columns(fieldnames)
        self._validate_rows(rows)

        dates = [datetime.strptime(row["date"], "%Y-%m-%d") for row in rows]

        for index in range(1, len(dates)):
            if dates[index] < dates[index - 1]:
                data_row = len(rows) - index + 1
                raise ValueError(
                    f"{self.file_path}: transactions must be newest-first; data row {data_row} breaks order"
                )

        for row, date in zip(rows, dates, strict=True):
            try:
                amount = Decimal(row["amount"])
            except InvalidOperation:
                raise ValueError(f"invalid transaction amount '{row['amount']}'") from None

            if amount == 0:
                raise ValueError("transaction amount is zero")

            if amount > 0:
                try:
                    rate = Decimal(f"{row['rate']}")
                except InvalidOperation:
                    raise ValueError(f"invalid transaction rate '{row['rate']}'") from None
                self.account.deposit(date=date, amount=amount, rate=rate)
            else:
                self.account.withdraw(
                    date=date,
                    amount=amount * -1,
                    description=row["description"],
                )
