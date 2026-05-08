"""``bim doc rules validate`` — static validation of issuers.yml rule blocks."""

from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult
from pydantic import ValidationError

from bim.commands.doc.shared.issuers import load_registry

__all__ = ["CommandRulesValidate"]


def _format_validation_error(exc: ValidationError) -> str:
    lines: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        lines.append(f"  {loc}: {err['msg']}")
    return "validation errors:\n" + "\n".join(lines)


class CommandRulesValidate:
    """Statically validate issuers.yml rule blocks via the existing loader."""

    def run(self, issuers_path: Path) -> CommandResult:
        if not issuers_path.is_file():
            return CommandResult(success=False, error=f"issuers file not found: {issuers_path}")

        try:
            registry = load_registry(issuers_path)
        except ValidationError as exc:
            return CommandResult(success=False, error=_format_validation_error(exc))
        except (RuntimeError, ValueError) as exc:
            return CommandResult(success=False, error=str(exc))

        rule_count = sum(len(entry.rules) for entry in registry.issuers.values())
        issuer_count = len(registry.issuers)
        return CommandResult(
            success=True,
            output=f"OK. Loaded {rule_count} rule(s) across {issuer_count} issuer(s).",
        )
