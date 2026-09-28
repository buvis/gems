from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ServeParams(BaseModel):
    """Parameters for the serve command."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    default_directory: str = Field(..., description="Default zettelkasten directory path")
    archive_directory: str | None = Field(None, description="Archive directory path")
    host: str = Field("127.0.0.1", description="Server host")
    port: int = Field(8000, description="Server port")
    no_browser: bool = Field(False, description="Skip opening browser")
    business_triage_root: str | None = Field(
        None, description="The <business_root>/_triage/ directory (doc triage actions), if [doc] is configured"
    )
    doc_settings: Any = Field(None, description="DocSettings for doc-action handlers, if [doc] is configured")
