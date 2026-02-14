from __future__ import annotations

import datetime
from decimal import Decimal

from fctracker.domain.deposit import Deposit
from fctracker.domain.quantified_queue import QuantifiedQueue
from fctracker.domain.withdrawal import Withdrawal


class Account:
    def __init__(
        self,
        name: str,
        currency: str,
        precision: int,
        symbol: str,
        local_precision: int,
        local_symbol: str,
    ) -> None:
        self.name = name
        self.currency = currency
        self.precision = precision
        self.symbol = symbol
        self.local_precision = local_precision
        self.local_symbol = local_symbol
        self._store: QuantifiedQueue[Deposit] = QuantifiedQueue()
        self.transactions: list[Deposit | Withdrawal] = []

    def deposit(self, date: datetime.date, amount: Decimal, rate: Decimal) -> None:
        deposit_transaction = Deposit(date, amount, self.currency, rate)
        self._store.put(deposit_transaction)
        self.transactions.append(deposit_transaction)

    def withdraw(self, date: datetime.date, amount: Decimal, description: str) -> Withdrawal:
        withdrawn_deposits = self._store.get(amount)
        local_cost = Decimal("0")

        for wd in withdrawn_deposits:
            local_cost += wd.amount * wd.rate

        rate = local_cost / amount

        withdrawal_transaction = Withdrawal(date, amount, self.currency, rate, description)
        self.transactions.append(withdrawal_transaction)

        return withdrawal_transaction

    def get_balance(self) -> Decimal:
        balance = Decimal("0")

        for deposit in self._store:
            balance += Decimal(f"{deposit.amount}")

        return Decimal(f"{balance:.{self.precision}f}")

    def get_balance_local(self) -> Decimal:
        balance = Decimal("0")

        for deposit in self._store:
            balance += Decimal(f"{deposit.amount}") * Decimal(f"{deposit.rate}")

        return Decimal(f"{balance:.{self.local_precision}f}")

    def __repr__(self) -> str:
        bal = self.get_balance()
        bal_local = self.get_balance_local()
        return (
            f"{self.name}[{self.currency}] balance: {bal} {self.symbol} "
            f"({bal_local} {self.local_symbol})"
        )
