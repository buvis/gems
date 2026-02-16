from __future__ import annotations

from typing import Any

from pydantic import Field

from bim.params.path_params import PathParams


class EditNoteParams(PathParams):
    """Parameters for the edit-note command."""

    changes: dict[str, Any] | None = Field(None, description="Metadata changes to apply")
    target: str = Field("metadata", description="Edit target section")
