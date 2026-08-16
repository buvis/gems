from __future__ import annotations

import queue
from decimal import InvalidOperation
from typing import Any

from buvis.pybase.result import CommandResult

from fctracker.adapters import TransactionsDirScanner, TransactionsReader
from fctracker.domain import Account, Deposit
from fctracker.settings import ForeignCurrencyConfig, LocalCurrencyConfig
from fctracker.shared import describe_transaction_error


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
        try:
            scanner = TransactionsDirScanner()
        except FileNotFoundError as exc:
            return CommandResult(success=False, error=str(exc))

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

                        tables.append(
                            {
                                "title": f"{account}, transactions",
                                "rows": self._build_rows(account),
                            }
                        )

        return CommandResult(success=True, metadata={"tables": tables})

    def _build_rows(self, account: Account) -> list[dict[str, str]]:
        """Build display rows for an account's filtered transactions.

        Args:
            account: The account whose transactions to filter and format.

        Returns:
            One row dict per filtered transaction, newest first, with a
            descending ``seq`` number starting at the filtered count.
        """
        filtered_transactions = [
            t for t in reversed(account.transactions) if (self.month == "" or t.is_in_month(self.month) is True)
        ]

        rows: list[dict[str, str]] = []
        index = len(filtered_transactions)

        for transaction in filtered_transactions:
            rows.append(self._build_row(transaction, index))
            index -= 1

        return rows

    def _build_row(self, transaction: Any, index: int) -> dict[str, str]:
        """Build a single display row for one transaction.

        Args:
            transaction: The transaction to render as a row.
            index: The descending sequence number for this row.

        Returns:
            A row dict with seq, date, description, amount, rate, outflow,
            and inflow fields.
        """
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
        return {
            "seq": str(index),
            "date": transaction.date.strftime("%Y-%m-%d"),
            "description": description,
            "amount": f"{transaction.amount} {transaction.currency_symbol}",
            "rate": rate_str,
            "outflow": outflow,
            "inflow": inflow,
        }
