"""HTTP chat backends: Ollama's ``/api/chat`` and OpenAI-compatible ``/v1/chat/completions``.

``ollama`` speaks Ollama's native chat API. ``llamacpp`` and ``openai`` speak
the OpenAI-compatible chat completions API. The call runs in a daemon worker
thread so the caller is released at the total deadline whatever the server does.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import TYPE_CHECKING, Any, Literal

from bim.shared.llm.base import (
    MAX_REPLY_BYTES,
    BackendError,
    BackendReason,
    LLMConfigError,
    parse_json_text,
    validate_payload,
    wire_schema,
)

if TYPE_CHECKING:
    from types import ModuleType

    from bim.shared.llm.base import LLMRequest, SchemaT
    from bim.shared.llm.settings import HttpBackendSettings

__all__ = ["HttpBackend", "build_chat_request", "read_chat_content"]

HttpKind = Literal["ollama", "llamacpp", "openai"]

_CHUNK_SIZE = 8192


def build_chat_request(
    kind: HttpKind,
    endpoint: str,
    model: str | None,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
) -> tuple[str, dict[str, object]]:
    """Return ``(url, body)`` for a non-streaming JSON-mode chat call; ``model`` is omitted when None."""
    base = endpoint.rstrip("/")
    head: dict[str, object] = {} if model is None else {"model": model}
    if kind == "ollama":
        return f"{base}/api/chat", {**head, "messages": messages, "format": "json", "stream": False}
    body: dict[str, object] = {
        **head,
        "messages": messages,
        # llama-server ignores {"type": "json_object"} and lets the model
        # wrap JSON in a ```json fence; a json_schema compiles a grammar.
        "response_format": {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema}},
    }
    if kind == "llamacpp":
        # Classification needs no reasoning trace; thinking only slows the
        # reply and can break the JSON grammar on Qwen3-style templates.
        body["chat_template_kwargs"] = {"enable_thinking": False}
    body["stream"] = False
    return f"{base}/v1/chat/completions", body


def read_chat_content(kind: HttpKind, payload: Any) -> str:
    """Return the assistant text.

    Raises:
        KeyError: The envelope lacks the expected keys, or ``choices`` is empty.
        TypeError: The envelope has the wrong shape, or the content is not text.
        IndexError: The envelope has the wrong shape.
    """
    if kind == "ollama":
        content = payload["message"]["content"]
    else:
        choices = payload["choices"]
        if not choices:
            raise KeyError("choices")
        content = choices[0]["message"]["content"]
    if not isinstance(content, str):
        msg = f"reply content is {type(content).__name__}, not text"
        raise TypeError(msg)
    return content


def _drop_redirect_target(response: Any, **_kwargs: Any) -> None:
    """Response hook: remove ``Location`` so requests never reads a redirect body.

    ``Session.send`` reads the whole body of a redirect that carries ``Location``, even with
    ``allow_redirects=False``, to prepare ``Response.next``. The hook runs before that step.
    """
    response.headers.pop("location", None)


class HttpBackend:
    """An HTTP chat endpoint; it has no tool access, so it is safe unattended."""

    unattended_safe = True

    def __init__(self, name: str, settings: HttpBackendSettings) -> None:
        self.name = name
        self._settings = settings

    def complete(
        self, request: LLMRequest, schema: type[SchemaT], *, timeout: float, model: str | None = None
    ) -> SchemaT:
        """Return the reply validated against ``schema``, or raise ``BackendError``.

        Raises:
            LLMConfigError: Neither the call nor the settings name a model (llamacpp runs without one).
        """
        kind = self._settings.kind
        chosen = model if model is not None else self._settings.model
        if chosen is None and kind != "llamacpp":
            msg = f"backend {self.name!r} has no model; set llm.{self.name}.model"
            raise LLMConfigError(msg)
        messages = [] if request.system is None else [{"role": "system", "content": request.system}]
        messages.append({"role": "user", "content": request.prompt})
        url, body = build_chat_request(kind, self._settings.endpoint, chosen, messages, wire_schema(schema))
        try:
            import requests
        except ImportError as exc:
            detail = "the 'requests' package is not installed; install buvis-gems[doc]"
            raise BackendError(BackendReason.EXIT, detail, backend=self.name) from exc
        payload = self._fetch(requests, url, body, timeout)
        try:
            text = read_chat_content(kind, payload)
        except (KeyError, TypeError, IndexError) as exc:
            raise BackendError(BackendReason.PARSE, f"malformed reply envelope: {exc}", backend=self.name) from exc
        return validate_payload(schema, parse_json_text(text, backend=self.name), backend=self.name)

    def _fetch(self, requests: ModuleType, url: str, body: dict[str, object], timeout: float) -> Any:
        """Run the call in a daemon worker; give up at the total deadline."""
        results: queue.Queue[Any] = queue.Queue(maxsize=1)
        cancelled = threading.Event()

        def work() -> None:
            """Put the decoded envelope or a ``BackendError`` on ``results``."""
            try:
                results.put(self._download(requests, url, body, timeout, cancelled))
            except BackendError as exc:
                results.put(exc)
            except requests.exceptions.Timeout as exc:
                detail = f"no reply from {url} within {timeout}s: {exc}"
                results.put(BackendError(BackendReason.TIMEOUT, detail, backend=self.name))
            except Exception as exc:
                results.put(BackendError(BackendReason.EXIT, f"HTTP error calling {url}: {exc}", backend=self.name))

        threading.Thread(target=work, daemon=True).start()
        try:
            outcome = results.get(timeout=timeout)
        except queue.Empty:
            detail = f"no complete reply from {url} within {timeout}s"
            raise BackendError(BackendReason.TIMEOUT, detail, backend=self.name) from None
        finally:
            cancelled.set()
        if isinstance(outcome, BackendError):
            raise outcome
        return outcome

    def _download(
        self, requests: ModuleType, url: str, body: dict[str, object], timeout: float, cancelled: threading.Event
    ) -> Any:
        """Post ``body`` and return the decoded envelope; ``None`` once the caller has gone."""
        response = requests.post(
            url,
            json=body,
            timeout=timeout,
            stream=True,
            allow_redirects=False,
            hooks={"response": _drop_redirect_target},
        )
        try:
            if 300 <= response.status_code < 400:
                detail = f"redirect not followed: {url} answered {response.status_code}"
                raise BackendError(BackendReason.EXIT, detail, backend=self.name)
            response.raise_for_status()
            buffer = bytearray()
            for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                if cancelled.is_set():
                    return None
                buffer += chunk
                if len(buffer) > MAX_REPLY_BYTES:
                    detail = f"reply larger than {MAX_REPLY_BYTES} bytes from {url}"
                    raise BackendError(BackendReason.EXIT, detail, backend=self.name)
            return json.loads(bytes(buffer))
        finally:
            response.close()
