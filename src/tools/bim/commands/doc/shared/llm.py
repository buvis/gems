"""Doc LLM route and chat wire format.

``resolve_doc_route`` maps ``doc.classifier`` onto the shared ``llm:`` map.
A ``backend`` that names an ``llm:`` entry routes there (named mode). The
legacy words ``ollama`` and ``llamacpp`` keep the old single-endpoint setup
with ``primary_model`` and ``fallback_model`` (legacy mode).

``chat_request`` and ``chat_content`` shape the legacy wire format: ``ollama``
speaks Ollama's native ``/api/chat``, ``llamacpp`` speaks llama-server's
OpenAI-compatible ``/v1/chat/completions``. Callers keep their own transport
and error handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from bim.shared.llm import HttpBackendSettings, LLMConfigError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from bim.commands.doc.shared.settings_models import ClassifierSettings
    from bim.shared.llm import ClaudeBackendSettings, CommandBackendSettings

__all__ = [
    "DOC_REQUEST_TIMEOUT_SECONDS",
    "LEGACY_DOC_BACKENDS",
    "DocLLMRoute",
    "DocLLMTarget",
    "chat_content",
    "chat_request",
    "resolve_doc_route",
]

LEGACY_DOC_BACKENDS: frozenset[str] = frozenset({"ollama", "llamacpp"})
DOC_REQUEST_TIMEOUT_SECONDS: float = 60


@dataclass(frozen=True)
class DocLLMTarget:
    """One doc LLM call target.

    Attributes:
        backend: Name of the entry in the route's backends.
        model: Call-time model override; ``None`` uses the entry's own model.
        key: The string the retry helper passes around.
    """

    backend: str
    model: str | None
    key: str


@dataclass(frozen=True)
class DocLLMRoute:
    """The resolved primary and fallback targets for doc classification."""

    primary: DocLLMTarget
    fallback: DocLLMTarget
    legacy: bool
    backends: Mapping[str, ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings]

    def target(self, key: str) -> DocLLMTarget:
        """Return the target for ``key``.

        Raises:
            LLMConfigError: In named mode, when ``key`` is neither target's key.
        """
        if key == self.fallback.key:
            return self.fallback
        if key == self.primary.key:
            return self.primary
        if self.legacy:
            return DocLLMTarget(backend=self.primary.backend, model=key, key=key)
        raise LLMConfigError(f"doc llm key {key!r} is neither the primary nor the fallback llm entry")


def resolve_doc_route(
    classifier: ClassifierSettings,
    llm: Mapping[str, ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings],
) -> DocLLMRoute:
    """Resolve ``doc.classifier`` against the ``llm:`` map.

    Raises:
        LLMConfigError: When the backend or fallback name resolves to nothing.
    """
    backend = classifier.backend
    if backend in llm:
        fallback = classifier.fallback or backend
        if fallback not in llm:
            raise LLMConfigError(f"doc.classifier.fallback {fallback!r} is not an llm entry")
        return DocLLMRoute(
            primary=DocLLMTarget(backend=backend, model=None, key=backend),
            fallback=DocLLMTarget(backend=fallback, model=None, key=fallback),
            legacy=False,
            backends=dict(llm),
        )
    if backend not in LEGACY_DOC_BACKENDS:
        raise LLMConfigError(
            f"doc.classifier.backend {backend!r} is neither an llm entry nor one of {sorted(LEGACY_DOC_BACKENDS)}"
        )
    if classifier.fallback is not None:
        raise LLMConfigError("doc.classifier.fallback needs doc.classifier.backend to name an llm entry")
    synthetic = HttpBackendSettings(
        kind="llamacpp" if backend == "llamacpp" else "ollama",
        endpoint=classifier.endpoint,
    )
    return DocLLMRoute(
        primary=DocLLMTarget(backend=backend, model=classifier.primary_model, key=classifier.primary_model),
        fallback=DocLLMTarget(backend=backend, model=classifier.fallback_model, key=classifier.fallback_model),
        legacy=True,
        backends={backend: synthetic},
    )


def chat_request(
    settings: ClassifierSettings,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[str, dict[str, object]]:
    """Return ``(url, body)`` for a non-streaming JSON-mode chat call."""
    base = settings.endpoint.rstrip("/")
    if settings.backend == "llamacpp":
        return f"{base}/v1/chat/completions", {
            "model": model,
            "messages": messages,
            # llama-server ignores {"type": "json_object"} and lets the model
            # wrap JSON in a ```json fence; a json_schema compiles a grammar.
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "reply", "schema": {"type": "object"}},
            },
            # Classification needs no reasoning trace; thinking only slows the
            # reply and can break the JSON grammar on Qwen3-style templates.
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }
    return f"{base}/api/chat", {
        "model": model,
        "messages": messages,
        "format": "json",
        "stream": False,
    }


def chat_content(settings: ClassifierSettings, payload: Any) -> Any:
    """Return the assistant text. Raises ``KeyError``/``TypeError`` on a malformed reply."""
    if settings.backend == "llamacpp":
        choices = payload["choices"]
        if not choices:
            raise KeyError("choices")
        return choices[0]["message"]["content"]
    return payload["message"]["content"]
