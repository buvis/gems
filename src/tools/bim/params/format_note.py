from __future__ import annotations

from pathlib import Path

from pydantic import Field

from bim.params.path_params import PathParams


class FormatNoteParams(PathParams):
    """Parameters for the format-note command."""

    path_output: Path | None = Field(None, description="Output file path")
