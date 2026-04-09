"""Base settings models and security mixins for tool-specific configuration."""

from __future__ import annotations

import os
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .validators import _SENSITIVE_PATTERNS, _ModelFieldsOwner, validate_json_env_size

__all__ = ["GlobalSettings", "SafeLoggingMixin", "SecureSettingsMixin", "ToolSettings"]


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
    auto_update: bool = True
    installer: str | None = None
    ollama_model: str | None = None
    ollama_url: str = "http://localhost:11434"
    adapters: dict[str, dict[str, Any]] = {}


class SecureSettingsMixin:
    """Mixin adding security validations for settings.

    Validates JSON env values don't exceed 64KB.

    Example::

        class MySettings(SecureSettingsMixin, BaseSettings):
            ...
    """

    @model_validator(mode="before")
    @classmethod
    def validate_json_sizes(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Check env var sizes before parsing."""
        config = getattr(cls, "model_config", {})
        prefix = config.get("env_prefix", "")

        for key in os.environ:
            if key.startswith(prefix):
                validate_json_env_size(key)

        return data


class SafeLoggingMixin:
    """Mixin that sanitizes sensitive values in __repr__.

    Masks values for fields whose names match sensitive patterns like
    'api_key', 'password', 'token', 'authorization', etc.
    """

    def __repr__(self) -> str:
        """Repr with sensitive values masked."""
        fields = []
        model_fields = cast(_ModelFieldsOwner, self.__class__).model_fields
        for name in model_fields:
            value = getattr(self, name, None)
            if _SENSITIVE_PATTERNS.search(name):
                fields.append(f"{name}='***'")
            elif isinstance(value, dict):
                safe_dict = {k: "***" if _SENSITIVE_PATTERNS.search(str(k)) else v for k, v in value.items()}
                fields.append(f"{name}={safe_dict}")
            else:
                fields.append(f"{name}={value!r}")
        return f"{self.__class__.__name__}({', '.join(fields)})"
