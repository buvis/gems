import queue
from decimal import Decimal

import pytest
from fctracker.domain import QuantifiedItem, QuantifiedQueue


class NumberedItem(QuantifiedItem):
    def __init__(self, quantity, number):
        self.quantity = Decimal(f"{quantity}")
        self.number = number

    def get_quantity(self):
        return self.quantity

    def set_quantity(self, value):
        self.quantity = value

    def __copy__(self):
        return type(self)(self.quantity, self.number)

    def __repr__(self):
        return f"({self.quantity}, {self.number})"


def test_get_full():
    qq = QuantifiedQueue()

    qq.put(NumberedItem(5, 1))
    items = qq.get(5)
    assert items[0].quantity == 5
    assert items[0].number == 1

    qq.put(NumberedItem(6, 2))
    qq.put(NumberedItem(7, 3))
    items = qq.get(6)
    assert items[0].quantity == 6
    assert items[0].number == 2

    qq.put(NumberedItem(8, 4))
    items = qq.get(7)
    assert items[0].quantity == 7
    assert items[0].number == 3
    items = qq.get(8)
    assert items[0].quantity == 8
    assert items[0].number == 4


def test_get_partial():
    qq = QuantifiedQueue()

    qq.put(NumberedItem(10.42, 24.4988))
    qq.put(NumberedItem(207.63, 24.5847))

    items = qq.get(207.63)
    assert items[0].quantity == Decimal("10.42")
    assert items[1].quantity == Decimal("197.21")
    assert items[0].number == 24.4988
    assert items[1].number == 24.5847
    assert qq.empty() is False

    items = qq.get(10.42)
    assert items[0].quantity == Decimal("10.42")
    assert items[0].number == 24.5847
    assert qq.empty() is True


def test_get_more_than_available():
    qq = QuantifiedQueue()

    qq.put(NumberedItem(207.63, 24.5847))

    with pytest.raises(queue.Empty) as e:
        print(qq.get(207.64))

    assert e.errisinstance(queue.Empty) is True


def test_print():
    qq = QuantifiedQueue()

    qq.put(NumberedItem(10.42, 24.4988))
    qq.put(NumberedItem(207.63, 24.5847))
    qq.get(200)
    assert f"{qq}" == "[(18.05, 24.5847)]"
    qq.put(NumberedItem(18.05, 24.6368))
    assert f"{qq}" == "[(18.05, 24.5847), (18.05, 24.6368)]"
