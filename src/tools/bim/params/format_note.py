from __future__ import annotations

from pathlib import Path

from pydantic import Field

from bim.params.path_params import PathParams


class FormatNoteParams(PathParams):
    """Parameters for the format-note command."""

    highlight: bool = Field(
        False,
        description="Highlight formatted content",
        json_schema_extra={},
    )
    diff: bool = Field(
        False,
        description="Show original and formatted note side by side if different",
        json_schema_extra={"cli_short": "-d"},
    )
    path_output: Path | None = Field(
        None,
        description="Output file path",
        json_schema_extra={"cli_skip": True},
    )
