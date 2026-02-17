"""
This module defines the ZettelFileParser class and associated helper functions for parsing zettel files.

It includes functionality to extract metadata from filenames and file content using specific
patterns and external utilities.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.filesystem import FileMetadataReader
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.markdown import (
    MarkdownZettelFileParser,
)

DATETIME_PATTERN = re.compile(r"^\d{14}|\d{12}")


class ZettelFileParser:
    """A parser for zettel files that extracts raw data and metadata from the file content and filename.

    This parser uses the ZettelParserMarkdown for parsing the content of the file and enriches the parsed data
    with additional metadata extracted from the file path and system metadata.
    """

    @staticmethod
    def from_file(file_path: Path) -> ZettelData:
        """Parses a zettel file from a given path and returns the raw data with enriched metadata.

        Args:
            file_path: The path to the zettel file to be parsed.

        Returns:
            An object containing the parsed content and metadata of the zettel.
        """
        with file_path.open("r", encoding="utf-8") as file:
            content = file.read()

        zettel_raw_data = MarkdownZettelFileParser.parse(content)

        zettel_raw_data.metadata.setdefault("date", _get_date_from_file(file_path))
        zettel_raw_data.metadata.setdefault("title", _get_title_from_filename(file_path.stem))

        return zettel_raw_data


def _get_date_from_file(file_path: Path) -> datetime | None:
    """Attempts to extract a datetime object from the file name based on predefined patterns.
    If no valid date is found in the filename, it falls back to file system creation date or git first commit date.

    Args:
        file_path: The path to the file from which to extract the date.

    Returns:
        The extracted datetime object, if any, otherwise None.
    """
    if DATETIME_PATTERN.match(file_path.stem):
        for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M"):
            try:
                return datetime.strptime(file_path.stem[: len(fmt)], fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    fs_creation_date = FileMetadataReader.get_creation_datetime(file_path)
    git_first_commit_date = FileMetadataReader.get_first_commit_datetime(file_path)

    return min(filter(None, [fs_creation_date, git_first_commit_date]), default=None)


def _get_title_from_filename(filename: str) -> str | None:
    """Extracts a human-readable title from a filename by stripping away predefined patterns and formatting.

    Args:
        filename: The filename from which to extract the title.

    Returns:
        The extracted title, if any, otherwise None.
    """
    title_from_filename = DATETIME_PATTERN.sub("", filename).replace("-", " ").strip()
    return title_from_filename.capitalize() if title_from_filename else None
