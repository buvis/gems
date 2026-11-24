"""The shared LLM backend contract: request in, schema-validated payload out.

Nothing here prints, logs or exits; failures are raised as
:class:`BackendError` (operational) or :class:`LLMConfigError` (configuration).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, TypeVar, cast, runtime_checkable

from pydantic import BaseModel, RootModel, ValidationError

__all__ = [
    "MAX_REPLY_BYTES",
    "MAX_STDERR_BYTES",
    "Backend",
    "BackendError",
    "BackendReason",
    "JsonObject",
    "LLMConfigError",
    "LLMRequest",
    "SchemaT",
    "parse_json_text",
    "require_strict_schema",
    "validate_payload",
    "wire_schema",
]

MAX_REPLY_BYTES = 4 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024


class BackendReason(str, Enum):
    """Closed set of reasons a backend call can fail."""

    TIMEOUT = "timeout"
    EXIT = "exit"
    PARSE = "parse"
    SCHEMA = "schema"


class BackendError(RuntimeError):
    """A backend call failed, with a closed ``reason`` and a human ``detail``.

    Args:
        reason: A :class:`BackendReason` or its value; an unknown string raises ``ValueError``.
        detail: Free-text diagnostic.
        backend: Registry name of the backend that failed.
    """

    def __init__(self, reason: BackendReason | str, detail: str, *, backend: str) -> None:
        self.reason = BackendReason(reason)
        self.detail = detail
        self.backend = backend
        super().__init__(f"[{self.reason.value}] {backend}: {detail}")


class LLMConfigError(ValueError):
    """Unknown backend name, unattended refusal, or a schema type that does not forbid extra keys."""


@dataclass(frozen=True)
class LLMRequest:
    """One prompt, with an optional system text."""

    prompt: str
    system: str | None = None

    def as_text(self) -> str:
        """Return the request as one text (the stdin for CLI backends)."""
        if self.system is None:
            return self.prompt
        return f"{self.system}\n\n{self.prompt}"


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class JsonObject(RootModel[dict[str, Any]]):
    """Any JSON object. For callers (doc) that coerce fields themselves."""


@runtime_checkable
class Backend(Protocol):
    """The interface every LLM adapter implements."""

    name: str
    unattended_safe: bool

    def complete(
        self, request: LLMRequest, schema: type[SchemaT], *, timeout: float, model: str | None = None
    ) -> SchemaT:
        """Return the reply validated against ``schema``, or raise ``BackendError``."""
        ...


def wire_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Return the JSON schema sent to the backend for ``schema``."""
    if issubclass(schema, JsonObject):
        return {"type": "object"}
    return schema.model_json_schema()


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _find_open_object(node: Any, pointer: str) -> str | None:
    """Return the JSON pointer of the first object node that allows extra keys."""
    if not isinstance(node, dict):
        return None
    if "properties" in node and node.get("additionalProperties") is not False:
        return pointer
    children: list[tuple[str, Any]] = []
    for key in ("$defs", "properties"):
        children += [(f"{pointer}/{key}/{_escape(name)}", sub) for name, sub in node.get(key, {}).items()]
    for key in ("items", "additionalProperties"):
        if isinstance(node.get(key), dict):
            children.append((f"{pointer}/{key}", node[key]))
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        children += [(f"{pointer}/{key}/{index}", sub) for index, sub in enumerate(node.get(key, []))]
    for child_pointer, child in children:
        found = _find_open_object(child, child_pointer)
        if found is not None:
            return found
    return None


def require_strict_schema(schema: type[BaseModel]) -> None:
    """Raise ``LLMConfigError`` unless every object in ``schema`` forbids extra keys.

    ``JsonObject`` and its subclasses are accepted as is. An explicit
    ``dict[str, X]`` field is an open mapping and allowed.
    """
    if issubclass(schema, JsonObject):
        return
    found = _find_open_object(schema.model_json_schema(), "#")
    if found is not None:
        msg = f"schema {schema.__name__} allows unexpected keys at {found}; set extra='forbid'"
        raise LLMConfigError(msg)


def parse_json_text(text: object, *, backend: str) -> Any:
    """Parse reply text as one JSON document, or raise a ``parse`` ``BackendError``.

    A non-string ``text`` (e.g. a null ``content``) makes ``json.loads`` raise ``TypeError``.
    """
    try:
        return json.loads(cast(str, text))
    except (json.JSONDecodeError, TypeError) as exc:
        raise BackendError(BackendReason.PARSE, f"reply is not valid JSON: {exc}", backend=backend) from exc


def validate_payload(schema: type[SchemaT], data: Any, *, backend: str) -> SchemaT:
    """Validate ``data`` against ``schema``, or raise a ``schema`` ``BackendError``."""
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        detail = f"reply does not match {schema.__name__}: {exc}"
        raise BackendError(BackendReason.SCHEMA, detail, backend=backend) from exc
