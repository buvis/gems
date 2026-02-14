from buvis.pybase.adapters import console
from fctracker.adapters import TransactionsDirScanner, TransactionsReader
from fctracker.domain import Account
from fctracker.settings import FctrackerSettings


class CommandBalance:
    def __init__(self, settings: FctrackerSettings) -> None:
        self.settings = settings

    def execute(self) -> None:
        scanner = TransactionsDirScanner()

        for account_name, currencies in scanner.accounts.items():
            for currency in currencies:
                fc = self.settings.foreign_currencies[currency]
                lc = self.settings.local_currency
                account = Account(
                    account_name, currency,
                    fc.precision, fc.symbol,
                    lc.precision, lc.symbol,
                )
                reader = TransactionsReader(account)
                reader.get_transactions()
                console.console.print(account)
