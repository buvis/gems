from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
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

            for row in rows:
                amount = Decimal(row["amount"])
                date = datetime.strptime(row["date"], "%Y-%m-%d")

                if amount > 0:
                    self.account.deposit(date=date, amount=amount, rate=Decimal(f"{row['rate']}"))
                else:
                    self.account.withdraw(
                        date=date,
                        amount=amount * -1,
                        description=row["description"],
                    )
