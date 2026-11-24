"""Per-kind settings for entries of the ``llm:`` config map."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "ClaudeBackendSettings",
    "CommandBackendSettings",
    "HttpBackendSettings",
    "LLMBackendSettings",
]


class ClaudeBackendSettings(BaseModel):
    """The ``claude`` CLI backend."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["claude"]
    model: str | None = None


class HttpBackendSettings(BaseModel):
    """An HTTP chat endpoint (Ollama, llama.cpp or OpenAI-compatible)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["ollama", "llamacpp", "openai"]
    endpoint: str
    model: str | None = None


class CommandBackendSettings(BaseModel):
    """A generic CLI driven by a literal argv, prompt on stdin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["command"]
    argv: list[str] = Field(min_length=1)
    unattended: bool = False

    @field_validator("argv")
    @classmethod
    def _no_empty_elements(cls, value: list[str]) -> list[str]:
        if any(not element for element in value):
            msg = "argv elements must be non-empty"
            raise ValueError(msg)
        return value


LLMBackendSettings = Annotated[
    ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings,
    Field(discriminator="kind"),
]
