"""Define MarkdownZettelFormatter for formatting Zettel data.

zettel.infrastructure.formatting.markdown_zettel_formatter.helpers"""

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

    This formatter adheres to the ZettelFormatter interface, ensuring that Zettel notes are formatted
    consistently with the expected Markdown structure.

    Attributes:
        TOP_KEYS: Keys considered top-level metadata in a Zettel note, used to structure the output.
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
        """Format the given Zettel data into a Markdown string.

        Args:
            zettel_data: The Zettel data to format.

        Returns:
            The formatted Zettel data as a Markdown string.
        """
        metadata_str: str = format_metadata(
            zettel_data.metadata,
            MarkdownZettelFormatter.TOP_KEYS,
        )
        reference_str: str = format_reference(zettel_data.reference)
        sections_str: str = format_sections(zettel_data.sections)

        return (f"---\n{metadata_str}\n---\n{sections_str}\n\n---\n{reference_str}").rstrip()
