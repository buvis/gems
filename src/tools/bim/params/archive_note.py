from __future__ import annotations

from pydantic import Field

from bim.params.path_params import PathParams


class ArchiveNoteParams(PathParams):
    """Parameters for the archive-note command."""

    undo: bool = Field(False, description="Unarchive (move back to zettelkasten)")
