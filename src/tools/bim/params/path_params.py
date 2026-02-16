from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class PathParams(BaseModel):
    """Base for commands that operate on resolved zettel paths."""

    paths: list[Path] = Field(..., min_length=1)
