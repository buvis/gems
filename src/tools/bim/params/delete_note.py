from __future__ import annotations

from pydantic import Field

from bim.params.path_params import PathParams


class DeleteNoteParams(PathParams):
    """Parameters for the delete-note command."""

    force: bool = Field(False, description="Skip confirmation")
