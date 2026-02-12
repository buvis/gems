from __future__ import annotations

import datetime
from decimal import Decimal


class Transaction:
    def __init__(self, date: datetime.date | str, amount: Decimal, currency: str, rate: Decimal) -> None:
        if isinstance(date, datetime.date):
            self.date = date
        else:
            self.date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        self.amount = Decimal(f"{amount}")
        self.currency = currency
        self.rate = Decimal(f"{rate}")

    def is_in_month(self, month: str) -> bool:
        """Check if transaction's date falls to given month [YYYY-MM]"""
        parsed = datetime.datetime.strptime(month, "%Y-%m")

        return self.date.year == parsed.year and self.date.month == parsed.month
