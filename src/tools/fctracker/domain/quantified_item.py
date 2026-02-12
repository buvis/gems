from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal


class QuantifiedItem(ABC):
    @abstractmethod
    def __init__(self, quantity: Decimal) -> None:
        pass

    @abstractmethod
    def get_quantity(self) -> Decimal:
        pass

    @abstractmethod
    def set_quantity(self, value: Decimal) -> None:
        pass

    @abstractmethod
    def __copy__(self) -> QuantifiedItem:
        pass

    @abstractmethod
    def __repr__(self) -> str:
        pass
