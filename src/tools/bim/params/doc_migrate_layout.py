from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MigrateLayoutParams(BaseModel):
    """Parameters for the ``bim doc migrate-layout`` command.

    Migrates legacy flat-layout document zettels into their per-issuer
    subfolder, preserving each file's content (including the ``file-path``
    frontmatter link) byte-for-byte — only the file moves.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dry_run: bool = Field(
        True,
        description="Plan only (print planned moves), do not touch the filesystem. Default True.",
    )
