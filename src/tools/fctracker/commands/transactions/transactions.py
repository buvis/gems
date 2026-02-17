from __future__ import annotations

from typing import Any

from buvis.pybase.result import CommandResult

from fctracker.adapters import TransactionsDirScanner, TransactionsReader
from fctracker.domain import Account, Deposit
from fctracker.settings import ForeignCurrencyConfig, LocalCurrencyConfig


class CommandTransactions:
    def __init__(
        self,
        foreign_currencies: dict[str, ForeignCurrencyConfig],
        local_currency: LocalCurrencyConfig,
        account: str = "",
        currency: str = "",
        month: str = "",
    ) -> None:
        self.foreign_currencies = foreign_currencies
        self.local_currency = local_currency
        self.account = account.capitalize()
        self.currency = currency.upper()
        self.month = month

    def execute(self) -> CommandResult:
        scanner = TransactionsDirScanner()
        tables: list[dict[str, Any]] = []

        for account_name, currencies in scanner.accounts.items():
            if self.account in ("", account_name):
                for currency in currencies:
                    if self.currency in ("", currency):
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

                        filtered_transactions = [
                            t
                            for t in reversed(account.transactions)
                            if (self.month == "" or t.is_in_month(self.month) is True)
                        ]

                        rows: list[dict[str, str]] = []
                        index = len(filtered_transactions)

                        for transaction in filtered_transactions:
                            if isinstance(transaction, Deposit):
                                description = "Deposit"
                                outflow = ""
                                inflow = f"{transaction.get_local_cost()} {self.local_currency.symbol}"
                            else:
                                description = transaction.description
                                outflow = f"{transaction.get_local_cost()} {self.local_currency.symbol}"
                                inflow = ""
                            precision = self.local_currency.precision * 2
                            local_sym = self.local_currency.symbol
                            rate_str = f"{transaction.rate:.{precision}f} {local_sym}/{transaction.currency_symbol}"
                            rows.append(
                                {
                                    "seq": str(index),
                                    "date": transaction.date.strftime("%Y-%m-%d"),
                                    "description": description,
                                    "amount": f"{transaction.amount} {transaction.currency_symbol}",
                                    "rate": rate_str,
                                    "outflow": outflow,
                                    "inflow": inflow,
                                }
                            )
                            index -= 1

                        tables.append(
                            {
                                "title": f"{account}, transactions",
                                "rows": rows,
                            }
                        )

        return CommandResult(success=True, metadata={"tables": tables})
