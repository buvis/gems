"""
This module defines the MarkdownZettelFormatter class which implements the :class:`ZettelFormatter` interface.

Imports:
    - :class:`ZettelFormatter` from buvis.pybase.zettel.domain.interfaces.zettel_formatter
    - :class:`ZettelData` from buvis.pybase.zettel.domain.value_objects.zettel_data
    - Helper functions (format_metadata, format_reference, format_sections) from
    zettel.infrastructure.formatting.markdown_zettel_formatter.helpers
"""

from __future__ import annotations

from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.helpers import (
    format_metadata,
    format_reference,
    format_sections,
)


class MarkdownZettelFormatter(ZettelFormatter):
    """
    Format Zettel notes into Markdown using provided Zettel data.

    This formatter adheres to the :class:`ZettelFormatter` interface, ensuring that Zettel notes are formatted
    consistently with the expected Markdown structure.

    :ivar TOP_KEYS: Keys considered top-level metadata in a Zettel note, used to structure the output.
    :type TOP_KEYS: tuple
    """

    TOP_KEYS: tuple[str, ...] = (
        "id",
        "title",
        "date",
        "type",
        "tags",
        "publish",
        "processed",
    )

    @staticmethod
    def format(zettel_data: ZettelData) -> str:
        """
        Format the given Zettel data into a Markdown string.

        :param zettel_data: The Zettel data to format.
        :type zettel_data: :class:`ZettelData`
        :return: The formatted Zettel data as a Markdown string.
        :rtype: str
        """
        metadata_str: str = format_metadata(
            zettel_data.metadata,
            MarkdownZettelFormatter.TOP_KEYS,
        )
        reference_str: str = format_reference(zettel_data.reference)
        sections_str: str = format_sections(zettel_data.sections)

        return (f"---\n{metadata_str}\n---\n{sections_str}\n\n---\n{reference_str}").rstrip()
