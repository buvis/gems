from __future__ import annotations

import queue
from decimal import InvalidOperation

from buvis.pybase.result import CommandResult

from fctracker.adapters import TransactionsDirScanner, TransactionsReader
from fctracker.domain import Account
from fctracker.settings import ForeignCurrencyConfig, LocalCurrencyConfig
from fctracker.shared import describe_transaction_error


class CommandBalance:
    def __init__(
        self,
        foreign_currencies: dict[str, ForeignCurrencyConfig],
        local_currency: LocalCurrencyConfig,
    ) -> None:
        self.foreign_currencies = foreign_currencies
        self.local_currency = local_currency

    def execute(self) -> CommandResult:
        try:
            scanner = TransactionsDirScanner()
        except FileNotFoundError as exc:
            return CommandResult(success=False, error=str(exc))

        accounts: list[Account] = []

        for account_name, currencies in scanner.accounts.items():
            for currency in currencies:
                fc = self.foreign_currencies[currency]
                account = Account(
                    account_name,
                    currency,
                    fc.precision,
                    fc.symbol,
                    self.local_currency.precision,
                    self.local_currency.symbol,
                )
                try:
                    reader = TransactionsReader(account)
                    reader.get_transactions()
                except FileNotFoundError as exc:
                    return CommandResult(success=False, error=str(exc))
                except (ValueError, queue.Empty, InvalidOperation) as exc:
                    return CommandResult(
                        success=False,
                        error=describe_transaction_error(account_name, exc),
                    )
                accounts.append(account)

        return CommandResult(
            success=True,
            metadata={"accounts": accounts},
        )
