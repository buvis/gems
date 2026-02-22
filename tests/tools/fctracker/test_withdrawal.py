from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch


def _mock_cfg():
    """Return a mock cfg with EUR and CZK configured."""
    cfg = MagicMock()
    cfg.currency = {"EUR": {"symbol": "\u20ac", "precision": 2}}
    cfg.local_currency = {"symbol": "K\u010d", "precision": 2}
    return cfg


class TestWithdrawal:
    def test_init(self) -> None:
        with patch("fctracker.adapters.config.config.cfg", _mock_cfg()):
            from fctracker.domain.withdrawal import Withdrawal

            w = Withdrawal(
                date=datetime.date(2024, 3, 15),
                amount=Decimal("50"),
                currency="EUR",
                rate=Decimal("25.50"),
                description="Amazon",
            )

        assert w.amount == Decimal("50")
        assert w.rate == Decimal("25.50")
        assert w.description == "Amazon"
        assert w.currency_symbol == "\u20ac"

    def test_repr(self) -> None:
        with patch("fctracker.adapters.config.config.cfg", _mock_cfg()):
            from fctracker.domain.withdrawal import Withdrawal

            w = Withdrawal(
                date=datetime.date(2024, 3, 15),
                amount=Decimal("50"),
                currency="EUR",
                rate=Decimal("25.50"),
                description="Amazon",
            )
            repr_str = repr(w)

        assert "Amazon" in repr_str
        assert "50" in repr_str
        assert "2024-03-15" in repr_str

    def test_get_local_cost(self) -> None:
        with patch("fctracker.adapters.config.config.cfg", _mock_cfg()):
            from fctracker.domain.withdrawal import Withdrawal

            w = Withdrawal(
                date=datetime.date(2024, 3, 15),
                amount=Decimal("100"),
                currency="EUR",
                rate=Decimal("25.00"),
                description="Test",
            )
            cost = w.get_local_cost()

        assert cost == Decimal("2500.00")

    def test_copy(self) -> None:
        with patch("fctracker.adapters.config.config.cfg", _mock_cfg()):
            from fctracker.domain.withdrawal import Withdrawal

            w = Withdrawal(
                date=datetime.date(2024, 3, 15),
                amount=Decimal("50"),
                currency="EUR",
                rate=Decimal("25.50"),
                description="Amazon",
            )
            w2 = w.__copy__()

        assert w2.date == w.date
        assert w2.amount == w.amount
        assert w2.currency == w.currency
        assert w2.rate == w.rate
