import datetime
from decimal import Decimal

from fctracker.domain import Transaction


class TestTransaction:
    def test_init_with_date_string(self):
        t = Transaction("2024-01-15", 100, "EUR", 24.50)
        assert t.date == datetime.date(2024, 1, 15)
        assert t.amount == Decimal("100")
        assert t.currency == "EUR"
        assert t.rate == Decimal("24.50")

    def test_init_with_date_object(self):
        d = datetime.date(2024, 6, 1)
        t = Transaction(d, 50, "USD", 22.10)
        assert t.date == d

    def test_is_in_month_true(self):
        t = Transaction("2024-03-15", 100, "EUR", 24.50)
        assert t.is_in_month("2024-03") is True

    def test_is_in_month_false_different_month(self):
        t = Transaction("2024-03-15", 100, "EUR", 24.50)
        assert t.is_in_month("2024-04") is False

    def test_is_in_month_false_different_year(self):
        t = Transaction("2024-03-15", 100, "EUR", 24.50)
        assert t.is_in_month("2023-03") is False
