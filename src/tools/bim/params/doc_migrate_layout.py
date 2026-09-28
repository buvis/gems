from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MigrateLayoutParams(BaseModel):
    """Parameters for the ``bim doc migrate-layout`` command.

    Migrates legacy flat-layout document zettels into their per-issuer
    subfolder and rewrites the frontmatter to the v1 shape.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dry_run: bool = Field(
        True,
        description="Plan only (print planned moves), do not touch the filesystem. Default True.",
    )
