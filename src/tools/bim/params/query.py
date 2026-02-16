from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryParams(BaseModel):
    """Parameters for the query command."""

    model_config = {"arbitrary_types_allowed": True}

    spec: Any = Field(
        ...,
        description="Parsed query specification",
        json_schema_extra={"cli_skip": True},
    )
    default_directory: str = Field(
        ...,
        description="Default zettelkasten directory path",
        json_schema_extra={"cli_skip": True},
    )
    edit: bool = Field(
        False,
        description="Pick result with fzf and open in nvim",
        json_schema_extra={"cli_short": "-e"},
    )
    tui: bool = Field(False, description="Render output in interactive TUI")
