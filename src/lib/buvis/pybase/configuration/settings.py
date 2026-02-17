"""Base settings models for tool-specific configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["GlobalSettings", "ToolSettings"]


class ToolSettings(BaseModel):
    """Base for tool-specific settings.

    All tool namespaces inherit from this. Each tool gets enabled: bool = True.
    Subclasses add tool-specific fields. Uses BaseModel (not BaseSettings) since
    parent GlobalSettings handles ENV resolution.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True


class GlobalSettings(BaseSettings):
    """Global runtime settings for BUVIS tools.

    Loads from environment variables with ``BUVIS_`` prefix.
    Nested delimiter is ``__`` (e.g., ``BUVIS_PHOTO__LIBRARY_PATH``).
    """

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    output_format: Literal["text", "json", "yaml"] = "text"
    ollama_model: str | None = None
    ollama_url: str = "http://localhost:11434"
