"""
This module defines an abstract base class for formatting Zettel data.

Imports:
    - :class:`abc.ABC` and :class:`abc.abstractmethod` for creating abstract base classes and methods.
    - :class:`typing.TYPE_CHECKING` for type checking purposes.
    - :class:`zettel.domain.value_objects.zettel_data.ZettelData` for type annotations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ZettelFormatter(ABC):
    """
    Abstract base class to define the interface for Zettel data formatting.

    This class requires subclasses to implement the :meth:`format` method.
    """

    @staticmethod
    @abstractmethod
    def format(zettel_data: ZettelData) -> str:
        """
        Format the provided Zettel data into a string.

        :param zettel_data: The Zettel data to format
        :type zettel_data: :class:`zettel.domain.value_objects.zettel_data.ZettelData`
        :return: The formatted Zettel data as a string
        :rtype: str
        """
        pass
