"""
Module containing the PrintZettelUseCase class.

This module provides functionality for printing formatted Zettel data.
"""

from __future__ import annotations

from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class PrintZettelUseCase:
    """
    Use case for printing formatted Zettel data.

    This class encapsulates the logic for formatting and printing Zettel data
    using a provided ZettelFormatter.
    """

    def __init__(self: PrintZettelUseCase, formatter: ZettelFormatter) -> None:
        """Initialize the PrintZettelUseCase instance.

        Args:
            formatter: The ZettelFormatter to use for formatting Zettel data.
        """
        self.formatter = formatter

    def execute(self: PrintZettelUseCase, zettel_data: ZettelData) -> str:
        """Execute the use case by formatting the given Zettel data.

        Format the provided Zettel data using the configured formatter and
        return the result.

        Args:
            zettel_data: The Zettel data to format and print.

        Returns:
            The formatted Zettel data.
        """
        return self.formatter.format(zettel_data)
