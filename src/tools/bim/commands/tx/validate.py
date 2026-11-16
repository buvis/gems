"""``bim tx validate``: run every mechanical check over the tiromex folder."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from bim.commands.tx.shared.validator import validate_tiromex

if TYPE_CHECKING:
    from bim.commands.tx.shared.paths import TiromexPaths


class CommandTxValidate:
    """Validate the tiromex folder. ``as_json`` gives a machine-readable report.

    No errors give ``success=True``; any error gives ``success=False``.
    """

    def __init__(self, paths: TiromexPaths, *, as_json: bool = False, max_body_lines: int = 60) -> None:
        self.paths = paths
        self.as_json = as_json
        self.max_body_lines = max_body_lines

    def execute(self) -> CommandResult:
        """Validate and render the diagnostics as JSON or text."""
        errors = validate_tiromex(self.paths, max_body_lines=self.max_body_lines)

        if self.as_json:
            payload = {
                "clean": not errors,
                "error_count": len(errors),
                "errors": [{"path": e.path, "rule": e.rule, "message": e.message, "line": e.line} for e in errors],
            }
            output = json.dumps(payload, indent=2, sort_keys=True)
            return CommandResult(success=not errors, output=output, metadata={"error_count": len(errors)})

        if not errors:
            return CommandResult(success=True, output=f"tiromex is clean: {self.paths.folder}")

        lines = [f"{e.path}: [{e.rule}] {e.message}" for e in errors]
        return CommandResult(
            success=False,
            error=f"{len(errors)} validation error(s):\n" + "\n".join(lines),
            metadata={"error_count": len(errors)},
        )
