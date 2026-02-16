from __future__ import annotations

from pydantic import Field

from bim.params.path_params import PathParams


class ImportNoteParams(PathParams):
    """Parameters for the import-note command."""

    tags: list[str] | None = Field(None, description="Tags to apply to imported note")
    force: bool = Field(False, description="Overwrite if target exists")
    remove_original: bool = Field(False, description="Delete source after import")
