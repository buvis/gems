"""
Module containing the PrintZettelUseCase class.

This module provides functionality for printing formatted Zettel data.
"""

from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class PrintZettelUseCase:
    """
    Use case for printing formatted Zettel data.

    This class encapsulates the logic for formatting and printing Zettel data
    using a provided ZettelFormatter.
    """

    def __init__(self: "PrintZettelUseCase", formatter: ZettelFormatter) -> None:
        """
        Initialize the PrintZettelUseCase instance.

        :param formatter: The ZettelFormatter to use for formatting Zettel data.
        :type formatter: :class:`zettel.domain.interfaces.zettel_formatter.ZettelFormatter`
        """
        self.formatter = formatter

    def execute(self: "PrintZettelUseCase", zettel_data: ZettelData) -> None:
        """
        Execute the use case by formatting and printing the given Zettel data.

        Format the provided Zettel data using the configured formatter and print
        the result.

        :param zettel_data: The Zettel data to format and print.
        :type zettel_data: :class:`zettel.domain.value_objects.zettel_data.ZettelData`
        :return: None
        :rtype: None
        """
        print(self.formatter.format(zettel_data))
