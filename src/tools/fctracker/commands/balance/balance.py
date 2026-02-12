from buvis.pybase.adapters import console
from fctracker.adapters import TransactionsDirScanner, TransactionsReader
from fctracker.domain import Account


class CommandBalance:
    def __init__(self) -> None:
        pass

    def execute(self) -> None:
        scanner = TransactionsDirScanner()

        for account_name, currencies in scanner.accounts.items():
            for currency in currencies:
                account = Account(account_name, currency)
                reader = TransactionsReader(account)
                reader.get_transactions()
                console.print(account)
