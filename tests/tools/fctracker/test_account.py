from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fctracker.domain import Account


class TestAccount:
    def test_get_balance(self):
        account = Account("Revolut", "EUR", 2, "€", 2, "Kč")
        now = datetime.now()
        account.deposit(now, 20, 24.4988)
        assert account.get_balance() == Decimal("20")

    def test_get_balance_local(self):
        account = Account("Revolut", "EUR", 2, "€", 2, "Kč")
        now = datetime.now()
        account.deposit(now, 20, 24.4988)
        assert account.get_balance_local() == Decimal("489.98")

    def test_print(self):
        account = Account("Revolut", "EUR", 2, "€", 2, "Kč")
        now = datetime.now()
        account.deposit(now, 20, 24.4988)
        assert f"{account}" == "Revolut[EUR] balance: 20.00 € (489.98 Kč)"

    def test_withdraw(self):
        account = Account("Revolut", "EUR", 2, "€", 2, "Kč")
        now = datetime.now()
        account.deposit(now, 20, 24.4988)
        account.deposit(now, 10, 24.3913)
        withdrawal = account.withdraw(now, 25, "Some expense")
        assert withdrawal.description == "Some expense"
        assert withdrawal.get_local_cost() == Decimal("611.93")
        assert account.get_balance_local() == Decimal("121.96")
