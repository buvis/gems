from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fctracker.adapters.config.config import cfg
from fctracker.domain.account import Account


class TransactionsReader:
    def __init__(self, account: Account) -> None:
        self.file_path = Path(
            cfg.transactions_dir,
            account.name.lower(),
            f"{account.currency.lower()}.csv",
        )
        self.account = account

    def get_transactions(self) -> None:
        with open(self.file_path) as csvfile:
            reader = csv.DictReader(csvfile, skipinitialspace=True)

            rows: list[dict[str, str]] = []

            for row in reader:
                rows.insert(0, row)

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
                    self.account.deposit(date=date, amount=amount, rate=Decimal(f"{row['rate']}"))
                else:
                    self.account.withdraw(
                        date=date,
                        amount=amount * -1,
                        description=row["description"],
                    )
