"""Shared, schema-checked LLM backends for bim. Adapters load lazily."""

from __future__ import annotations

from bim.shared.llm.base import Backend, BackendError, BackendReason, JsonObject, LLMConfigError, LLMRequest
from bim.shared.llm.registry import LLMRegistry, build_registry
from bim.shared.llm.settings import (
    ClaudeBackendSettings,
    CommandBackendSettings,
    HttpBackendSettings,
    LLMBackendSettings,
)

__all__ = [
    "Backend",
    "BackendError",
    "BackendReason",
    "ClaudeBackendSettings",
    "CommandBackendSettings",
    "HttpBackendSettings",
    "JsonObject",
    "LLMBackendSettings",
    "LLMConfigError",
    "LLMRegistry",
    "LLMRequest",
    "build_registry",
]
