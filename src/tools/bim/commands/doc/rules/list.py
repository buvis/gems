"""``bim doc rules list`` — print all rules across all issuers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from bim.commands.doc.shared.issuers import IssuerRegistry

__all__ = ["CommandRulesList"]


_HEADERS = ("id", "issuer", "version", "partial", "priority", "enabled")


class CommandRulesList:
    """List all rules in stable column order: id, issuer, version, partial, priority, enabled."""

    def run(self, registry: IssuerRegistry) -> CommandResult:
        rows: list[tuple[str, str, str, str, str, str]] = []
        for slug in sorted(registry.issuers.keys()):
            entry = registry.issuers[slug]
            for rule in entry.rules:
                rows.append(
                    (
                        rule.id,
                        slug,
                        str(rule.version),
                        "true" if rule.partial else "false",
                        str(rule.priority),
                        "true" if rule.enabled else "false",
                    )
                )
        if not rows:
            return CommandResult(success=True, output="No rules defined.")

        widths = [len(header) for header in _HEADERS]
        for row in rows:
            for index, value in enumerate(row):
                widths[index] = max(widths[index], len(value))

        def _fmt(values: tuple[str, ...]) -> str:
            return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))

        lines = [_fmt(_HEADERS), _fmt(tuple("-" * width for width in widths))]
        lines.extend(_fmt(row) for row in rows)
        return CommandResult(success=True, output="\n".join(lines))
