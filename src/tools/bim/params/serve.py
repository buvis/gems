from __future__ import annotations

from pydantic import BaseModel, Field


class ServeParams(BaseModel):
    """Parameters for the serve command."""

    default_directory: str = Field(..., description="Default zettelkasten directory path")
    archive_directory: str | None = Field(None, description="Archive directory path")
    host: str = Field("127.0.0.1", description="Server host")
    port: int = Field(8000, description="Server port")
    no_browser: bool = Field(False, description="Skip opening browser")
