from __future__ import annotations

from pydantic import Field

from bim.params.path_params import PathParams


class SyncNoteParams(PathParams):
    """Parameters for the sync-note command."""

    target_system: str = Field(..., description="Target system (e.g. jira)")
