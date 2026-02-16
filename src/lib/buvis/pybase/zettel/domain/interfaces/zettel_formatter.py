"""
This module defines an abstract base class for formatting Zettel data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ZettelFormatter(ABC):
    """Abstract base class to define the interface for Zettel data formatting.

    This class requires subclasses to implement the format method.
    """

    @staticmethod
    @abstractmethod
    def format(zettel_data: ZettelData) -> str:
        """Format the provided Zettel data into a string.

        Args:
            zettel_data: The Zettel data to format

        Returns:
            The formatted Zettel data as a string
        """
        pass
