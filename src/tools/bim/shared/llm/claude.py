"""Drive Claude Code headless as an LLM backend.

Runs ``claude -p --output-format json --json-schema <schema>`` with every
isolation flag (no tools, no MCP servers, safe mode, no slash commands, no
session transcript) and the request on stdin, through :func:`run_cli`.
Recheck the flags here when the operator CLI updates.
"""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, Any

from bim.shared.llm.base import (
    BackendError,
    BackendReason,
    parse_json_text,
    run_cli,
    validate_payload,
    wire_schema,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from bim.shared.llm.base import LLMRequest, SchemaT
    from bim.shared.llm.settings import ClaudeBackendSettings

__all__ = ["CLAUDE_TIMEOUT_CUSHION_SECONDS", "ClaudeBackend"]

CLAUDE_TIMEOUT_CUSHION_SECONDS = 30

_ISOLATION_FLAGS = [
    "--tools",
    "",
    "--strict-mcp-config",
    "--safe-mode",
    "--disable-slash-commands",
    "--no-session-persistence",
]


class ClaudeBackend:
    """The ``claude`` CLI adapter. Safe unattended because of its isolation flags."""

    unattended_safe = True

    def __init__(self, name: str, settings: ClaudeBackendSettings) -> None:
        self.name = name
        self.settings = settings

    def argv(self, schema: type[BaseModel], model: str | None) -> list[str]:
        """Return the claude argv for ``schema``; ``model`` overrides the settings model."""
        argv = ["claude", "-p", "--output-format", "json", "--json-schema", json.dumps(wire_schema(schema))]
        argv += _ISOLATION_FLAGS
        chosen = model or self.settings.model
        if chosen:
            argv += ["--model", chosen]
        return argv

    def complete(
        self, request: LLMRequest, schema: type[SchemaT], *, timeout: float, model: str | None = None
    ) -> SchemaT:
        """Return the reply validated against ``schema``, or raise ``BackendError``."""
        if shutil.which("claude") is None:
            raise BackendError(BackendReason.EXIT, "the 'claude' CLI is not on PATH", backend=self.name)
        stdout = run_cli(
            self.argv(schema, model),
            request.as_text(),
            timeout=timeout + CLAUDE_TIMEOUT_CUSHION_SECONDS,
            backend=self.name,
        )
        return validate_payload(schema, self._payload(stdout), backend=self.name)

    def _payload(self, stdout: str) -> Any:
        """Unwrap the JSON envelope; a bare payload is returned as is."""
        envelope = parse_json_text(stdout, backend=self.name)
        payload = envelope
        if isinstance(envelope, dict):
            if envelope.get("is_error"):
                result = envelope.get("result")
                detail = result if isinstance(result, str) else "claude reported an error without a message"
                raise BackendError(BackendReason.EXIT, detail, backend=self.name)
            if "structured_output" in envelope:
                payload = envelope["structured_output"]
            else:
                payload = envelope.get("result", envelope)
        if isinstance(payload, str):
            payload = parse_json_text(payload, backend=self.name)
        return payload
