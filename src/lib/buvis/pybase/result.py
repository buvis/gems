from __future__ import annotations

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
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict for API responses."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "warnings": self.warnings,
            "metadata": _json_safe(self.metadata),
        }
