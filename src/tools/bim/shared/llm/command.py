"""A user-configured command as an LLM backend: prompt on stdin, JSON on stdout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bim.shared.llm.base import parse_json_text, run_cli, validate_payload

if TYPE_CHECKING:
    from bim.shared.llm.base import LLMRequest, SchemaT
    from bim.shared.llm.settings import CommandBackendSettings

__all__ = ["CommandBackend"]


class CommandBackend:
    """Run ``settings.argv`` literally (no shell, no placeholders) with the request text on stdin.

    Args:
        name: Registry name of the backend.
        settings: The command and its unattended opt-in.
    """

    def __init__(self, name: str, settings: CommandBackendSettings) -> None:
        self.name = name
        self.unattended_safe = settings.unattended
        self._settings = settings

    def complete(
        self, request: LLMRequest, schema: type[SchemaT], *, timeout: float, model: str | None = None
    ) -> SchemaT:
        """Return the command's stdout validated against ``schema``; ``model`` is ignored."""
        del model
        stdout = run_cli(list(self._settings.argv), request.as_text(), timeout=timeout, backend=self.name)
        return validate_payload(schema, parse_json_text(stdout, backend=self.name), backend=self.name)
