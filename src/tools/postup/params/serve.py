"""Parameters for the ``postup serve`` command."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ServeParams"]


class ServeParams(BaseModel):
    """Validated parameters for ``postup serve``."""

    model_config = ConfigDict(frozen=True)

    host: str = Field("127.0.0.1", description="Interface to bind the server to.")
    port: int = Field(8000, ge=1, le=65535, description="TCP port to listen on.")
    no_browser: bool = Field(False, description="Skip opening the browser on start.")
