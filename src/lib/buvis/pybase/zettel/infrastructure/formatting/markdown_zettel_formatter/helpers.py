"""Module for processing and formatting metadata.

This module provides functions to process metadata dictionaries, convert datetime objects to strings,
format metadata into YAML, and handle string formatting in YAML outputs.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import yaml


def process_metadata(
    metadata: dict[str, Any],
    first_keys: tuple[str, ...],
) -> dict[str, Any]:
    """Process and return the full metadata with required keys first, followed by others.

    Args:
        metadata: The original metadata dictionary.
        first_keys: Tuple of keys which should appear first in the returned dictionary.

    Returns:
        Processed metadata dictionary with specified keys ordered first.
    """

    return {
        **{key: metadata[key] for key in first_keys if key in metadata},
        **{k: v for k, v in sorted(metadata.items()) if k not in first_keys},
    }


def convert_datetimes(full_metadata: dict[str, Any]) -> list[str]:
    """Convert datetime objects to formatted strings and return keys that were converted.

    Args:
        full_metadata: Metadata dictionary potentially containing datetime objects.

    Returns:
        List of keys for which the datetime values were converted.
    """
    datetime_keys = [key for key in full_metadata if isinstance(full_metadata[key], datetime)]

    for key in datetime_keys:
        full_metadata[key] = full_metadata[key].astimezone().replace(microsecond=0).isoformat()

    return datetime_keys


def metadata_to_yaml(
    full_metadata: dict[str, Any],
    datetime_keys: list[str],
) -> str:
    """Convert metadata dictionary to a YAML-formatted string without quotes on datetime keys.

    Args:
        full_metadata: Metadata dictionary with datetime objects converted to strings.
        datetime_keys: List of keys that have datetime values converted to strings.

    Returns:
        YAML formatted string with unquoted datetime values.
    """
    metadata_str = yaml.dump(
        full_metadata,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    ).strip()
    datetime_regex = re.compile(rf"^({'|'.join(datetime_keys)}): '([^']*)'(.*)$", flags=re.MULTILINE)

    return datetime_regex.sub(r"\1: \2\3", metadata_str)


def format_metadata(metadata: dict[str, Any], first_keys: tuple[str, ...]) -> str:
    """Format the metadata into a YAML string with specified keys ordered first and datetimes unquoted.

    Args:
        metadata: The original metadata dictionary.
        first_keys: Tuple of keys which should appear first in the formatted output.

    Returns:
        Formatted YAML string.
    """
    full_metadata = process_metadata(metadata, first_keys)
    datetime_keys = convert_datetimes(full_metadata)
    metadata_str = metadata_to_yaml(full_metadata, datetime_keys)

    return metadata_str


def format_reference(reference: dict[str, Any]) -> str:
    """Format reference dictionary into a string with key-value pairs.

    Args:
        reference: Dictionary containing reference data.

    Returns:
        Formatted reference string.
    """
    formatted_reference = "\n"

    for key, value in reference.items():
        if value:
            formatted_reference += f"- {key}:: {str(value).lstrip()}\n"
        else:
            formatted_reference += f"- {key}::\n"

    return formatted_reference.rstrip()


def convert_markdown_to_preserve_line_breaks(text: str) -> str:
    r"""
    Convert multiline markdown text to preserve line breaks.

    This function adds two spaces at the end of each non-empty line in the
    input text to force line breaks in markdown, while preserving empty lines.

    Args:
        text: The input markdown text to be converted

    Returns:
        The converted markdown text with preserved line breaks

    Examples:
        >>> text = "Line one.\\nLine two.\\n\\nLine three."
        >>> print(convert_markdown_to_preserve_line_breaks(text))
        Line one.
        Line two.

        Line three.
    """
    lines = text.split("\n")  # Split the text into lines
    converted_lines = []

    for line in lines:
        if line.strip():  # Check if the line is not empty
            converted_lines.append(line + "  ")
        else:
            converted_lines.append(line)  # Preserve empty lines

    return "\n".join(converted_lines)  # Join the lines back into a single string


def format_sections(sections: list[tuple[str, str]]) -> str:
    """Format sections list into a string with headings and content.

    Args:
        sections: List of tuples containing section headings and content.

    Returns:
        Formatted sections string.
    """

    return "\n".join(
        f"\n{heading}\n\n{convert_markdown_to_preserve_line_breaks(content.strip())}"
        if content.strip()
        else f"\n{heading}"
        for heading, content in sections
    )
