from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any


def _json_safe(obj: Any) -> Any:
    """Recursively convert non-serializable types for JSON output.

    Args:
        obj: Value to convert.

    Returns:
        JSON-safe value.
    """
    if isinstance(obj, PurePath):
        return str(obj)
    if isinstance(obj, dict):
        return {key: _json_safe(value) for key, value in obj.items()}
    if isinstance(obj, list | tuple):
        return [_json_safe(value) for value in obj]
    return obj


class FatalError(Exception):
    """Raised by commands for unrecoverable errors (missing config, missing deps)."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Standardized command result payload."""

    success: bool
    output: str | None = None
    error: str | None = None
    info: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict for API responses."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "info": self.info,
            "warnings": self.warnings,
            "metadata": _json_safe(self.metadata),
        }


def notify_result(result: CommandResult, notify: Callable[..., None]) -> None:
    """Report a command result through a Textual-style notify callback.

    Args:
        result: Command result to report.
        notify: Callable accepting ``(message, *, severity)``, e.g. Textual's
            ``App.notify``.
    """
    for warning in result.warnings:
        notify(warning, severity="warning")
    if result.success:
        if result.output:
            notify(result.output, severity="information")
    else:
        notify(result.error or "Failed", severity="error")
