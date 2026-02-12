import queue
from datetime import datetime
from decimal import Decimal

import pytest
from fctracker.domain import Deposit, QuantifiedQueue


def test_get_full():
    qq = QuantifiedQueue()

    now = datetime.now()

    qq.put(Deposit(now, 5, "EUR", 24.4988))
    items = qq.get(5)
    assert items[0].date == now
    assert items[0].amount == 5
    assert items[0].currency == "EUR"
    assert items[0].rate == Decimal("24.4988")

    qq.put(Deposit(now, 6, "EUR", 24.4988))
    qq.put(Deposit(now, 7, "EUR", 24.4888))
    items = qq.get(6)
    assert items[0].date == now
    assert items[0].amount == 6
    assert items[0].currency == "EUR"
    assert items[0].rate == Decimal("24.4988")

    qq.put(Deposit(now, 8, "EUR", 24.5888))
    items = qq.get(7)
    assert items[0].date == now
    assert items[0].amount == 7
    assert items[0].currency == "EUR"
    assert items[0].rate == Decimal("24.4888")

    items = qq.get(8)
    assert items[0].date == now
    assert items[0].amount == 8
    assert items[0].currency == "EUR"
    assert items[0].rate == Decimal("24.5888")


def test_get_partial():
    qq = QuantifiedQueue()

    now = datetime.now()

    qq.put(Deposit(now, 10.42, "EUR", 24.4988))
    qq.put(Deposit(now, 207.63, "EUR", 24.5847))

    items = qq.get(207.63)
    assert items[0].amount == Decimal("10.42")
    assert items[1].amount == Decimal("197.21")
    assert items[0].rate == Decimal("24.4988")
    assert items[1].rate == Decimal("24.5847")
    assert qq.empty() is False

    items = qq.get(10.42)
    assert items[0].amount == Decimal("10.42")
    assert items[0].rate == Decimal("24.5847")
    assert qq.empty() is True


def test_get_more_than_available():
    qq = QuantifiedQueue()

    now = datetime.now()
    qq.put(Deposit(now, 207.63, "EUR", 24.5847))

    with pytest.raises(queue.Empty) as e:
        qq.get(207.64)

    assert e.errisinstance(queue.Empty) is True


def test_print():
    qq = QuantifiedQueue()

    now = datetime.now()
    qq.put(Deposit(now, 10.42, "EUR", 24.4988))
    qq.put(Deposit(now, 207.63, "EUR", 24.5847))
    qq.get(200)
    assert f"{qq}" == f"[Added 18.05 € per 24.5847 Kč/€ (total 443.75 Kč) on {now.strftime('%Y-%m-%d')}]"
    qq.put(Deposit(now, 18.05, "EUR", 24.6368))
    d = now.strftime("%Y-%m-%d")
    expected = (
        f"[Added 18.05 € per 24.5847 Kč/€ (total 443.75 Kč) on {d}, "
        f"Added 18.05 € per 24.6368 Kč/€ (total 444.69 Kč) on {d}]"
    )
    assert f"{qq}" == expected
