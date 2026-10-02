"""``klyreon validate`` -- run every mechanical check over the whole vault."""

from __future__ import annotations

import json
from pathlib import Path

from buvis.pybase.result import CommandResult

from klyreon.spec.validator import validate_vault


class CommandValidate:
    """Validate the whole vault. ``as_json`` emits a machine-readable report.

    Success (no errors) returns ``success=True``; any error returns
    ``success=False`` so the CLI maps it to exit 1.
    """

    def __init__(self, root: Path, *, as_json: bool = False, max_body_lines: int = 60) -> None:
        self.root = root
        self.as_json = as_json
        self.max_body_lines = max_body_lines

    def execute(self) -> CommandResult:
        errors = validate_vault(self.root, max_body_lines=self.max_body_lines)

        if self.as_json:
            payload = {
                "clean": not errors,
                "error_count": len(errors),
                "errors": [{"path": e.path, "rule": e.rule, "message": e.message, "line": e.line} for e in errors],
            }
            output = json.dumps(payload, indent=2, sort_keys=True)
            return CommandResult(success=not errors, output=output, metadata={"error_count": len(errors)})

        if not errors:
            return CommandResult(success=True, output=f"vault is clean: {self.root}")

        lines = [f"{e.path}: [{e.rule}] {e.message}" for e in errors]
        return CommandResult(
            success=False,
            error=f"{len(errors)} validation error(s):\n" + "\n".join(lines),
            metadata={"error_count": len(errors)},
        )
