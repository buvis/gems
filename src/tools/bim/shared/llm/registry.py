"""Named LLM backends: config entries in, ready adapters out."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, cast

from bim.shared.llm.base import LLMConfigError, require_strict_schema

if TYPE_CHECKING:
    from collections.abc import Mapping

    from bim.shared.llm.base import Backend, LLMRequest, SchemaT
    from bim.shared.llm.settings import ClaudeBackendSettings, CommandBackendSettings, HttpBackendSettings

__all__ = ["LLMRegistry", "build_backend", "build_registry"]


class LLMRegistry:
    """Backends by configured name, with the unattended guard."""

    def __init__(self, backends: Mapping[str, Backend]) -> None:
        self._backends = dict(backends)

    def names(self) -> frozenset[str]:
        return frozenset(self._backends)

    def get(self, name: str, *, unattended: bool = False) -> Backend:
        """Return the backend named ``name``.

        Raises:
            LLMConfigError: The name is unknown, or the run is unattended and the backend is not safe for it.
        """
        backend = self._backends.get(name)
        if backend is None:
            msg = f"unknown LLM backend {name!r}; configured: {sorted(self._backends)}"
            raise LLMConfigError(msg)
        if unattended and not backend.unattended_safe:
            msg = (
                f"backend {name!r} cannot run unattended: a command backend cannot prove its tools are off; "
                f"set llm.{name}.unattended: true to accept that risk"
            )
            raise LLMConfigError(msg)
        return backend

    def invoke(
        self,
        name: str,
        request: LLMRequest,
        schema: type[SchemaT],
        *,
        timeout: float,
        model: str | None = None,
        unattended: bool = False,
    ) -> SchemaT:
        """Check ``schema``, then run ``request`` on the backend named ``name``."""
        require_strict_schema(schema)
        return self.get(name, unattended=unattended).complete(request, schema, timeout=timeout, model=model)


_ADAPTERS: dict[str, tuple[str, str]] = {
    "claude": ("bim.shared.llm.claude", "ClaudeBackend"),
    "command": ("bim.shared.llm.command", "CommandBackend"),
    "ollama": ("bim.shared.llm.http", "HttpBackend"),
    "llamacpp": ("bim.shared.llm.http", "HttpBackend"),
    "openai": ("bim.shared.llm.http", "HttpBackend"),
}


def build_backend(name: str, settings: ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings) -> Backend:
    """Build the adapter for one config entry; adapter modules load lazily."""
    module_name, class_name = _ADAPTERS[settings.kind]
    adapter = getattr(importlib.import_module(module_name), class_name)
    return cast("Backend", adapter(name, settings))


def build_registry(
    llm: Mapping[str, ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings],
) -> LLMRegistry:
    return LLMRegistry({name: build_backend(name, settings) for name, settings in llm.items()})
