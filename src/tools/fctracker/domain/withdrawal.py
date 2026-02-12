from __future__ import annotations

import datetime
from decimal import Decimal

from .transaction import Transaction


class Withdrawal(Transaction):
    def __init__(
        self,
        date: datetime.date,
        amount: Decimal,
        currency: str,
        rate: Decimal,
        description: str = "",
    ) -> None:
        from fctracker.adapters.config.config import cfg

        Transaction.__init__(self, date, amount, currency, rate)
        self.description = f"{description}"
        self.currency_symbol = cfg.currency[currency]["symbol"]

    def __copy__(self) -> Withdrawal:
        return type(self)(self.date, self.amount, self.currency, self.rate)

    def __repr__(self) -> str:
        from fctracker.adapters.config.config import cfg

        precision = cfg.local_currency["precision"]
        local_sym = cfg.local_currency["symbol"]
        rate_str = f"{self.rate:.{precision * 2}f} {local_sym}/{self.currency_symbol}"
        return (
            f"{self.description} for {self.amount} {self.currency_symbol} per {rate_str} "
            f"(total {self.get_local_cost()} {local_sym}) on {self.date.strftime('%Y-%m-%d')}"
        )

    def get_local_cost(self) -> Decimal:
        from fctracker.adapters.config.config import cfg

        return Decimal(f"{(self.amount * self.rate):.{cfg.local_currency['precision']}f}")
