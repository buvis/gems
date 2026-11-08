"""Chat wire format for the doc LLM backends.

``ollama`` speaks Ollama's native ``/api/chat``. ``llamacpp`` speaks
llama-server's OpenAI-compatible ``/v1/chat/completions``. Callers keep their
own transport and error handling; this module only shapes the request and
picks the reply text out of the response.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bim.commands.doc.shared.settings_models import ClassifierSettings

__all__ = ["chat_content", "chat_request"]


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
            "response_format": {"type": "json_object"},
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
