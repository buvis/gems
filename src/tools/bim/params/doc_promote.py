from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PromoteParams(BaseModel):
    """Parameters for the bim doc promote command.

    Promotes an approved triage proposal into a filed document and zettel.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposed_yml_path: Path = Field(..., description="Path to the .proposed.yml file to promote")
    dry_run: bool = Field(False, description="Plan only, do not move files or write zettel")
