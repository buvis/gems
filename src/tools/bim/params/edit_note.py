from __future__ import annotations

from typing import Any

from pydantic import Field

from bim.params.path_params import PathParams


class EditNoteParams(PathParams):
    """Parameters for the edit-note command."""

    changes: dict[str, Any] | None = Field(
        None,
        description="Metadata changes to apply",
        json_schema_extra={"cli_skip": True},
    )
    target: str = Field(
        "metadata",
        description="Edit target section",
        json_schema_extra={"cli_skip": True},
    )
    title: str | None = Field(None, description="New title")
    tags: str | None = Field(None, description="Comma-separated tags")
    zettel_type: str | None = Field(
        None,
        description="Note type",
        json_schema_extra={"cli_long": "--type"},
    )
    processed: bool | None = Field(None, description="Processed flag")
    publish: bool | None = Field(None, description="Publish flag")
