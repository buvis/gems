from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryParams(BaseModel):
    """Parameters for the query command."""

    model_config = {"arbitrary_types_allowed": True}

    spec: Any = Field(..., description="Parsed query specification")
    default_directory: str = Field(..., description="Default zettelkasten directory path")
