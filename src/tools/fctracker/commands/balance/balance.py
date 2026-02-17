from __future__ import annotations

from buvis.pybase.result import CommandResult

from fctracker.adapters import TransactionsDirScanner, TransactionsReader
from fctracker.domain import Account
from fctracker.settings import ForeignCurrencyConfig, LocalCurrencyConfig


class CommandBalance:
    def __init__(
        self,
        foreign_currencies: dict[str, ForeignCurrencyConfig],
        local_currency: LocalCurrencyConfig,
    ) -> None:
        self.foreign_currencies = foreign_currencies
        self.local_currency = local_currency

    def execute(self) -> CommandResult:
        scanner = TransactionsDirScanner()
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
                reader = TransactionsReader(account)
                reader.get_transactions()
                accounts.append(account)

        return CommandResult(
            success=True,
            metadata={"accounts": accounts},
        )
