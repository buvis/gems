"""``bim doc rules validate`` — static validation of issuers.yml rule blocks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from buvis.pybase.result import CommandResult
from pydantic import ValidationError

from bim.commands.doc.shared.issuers import load_registry

__all__ = ["CommandRulesValidate"]


def _resolve_rule_id(parsed: Any, loc: tuple[Any, ...]) -> str | None:
    """Walk parsed YAML by the validation-error path and return the rule's id
    if the path lands inside a rule. Returns None for non-rule errors or when
    the path can't be resolved.
    """
    if not (
        len(loc) >= 4
        and loc[0] == "issuers"
        and isinstance(loc[1], str)
        and loc[2] == "rules"
        and isinstance(loc[3], int)
    ):
        return None
    if not isinstance(parsed, dict):
        return None
    issuer_slug = loc[1]
    rule_index = loc[3]
    issuer_body = (parsed.get("issuers") or {}).get(issuer_slug)
    if not isinstance(issuer_body, dict):
        return None
    rules = issuer_body.get("rules")
    if not isinstance(rules, list) or not (0 <= rule_index < len(rules)):
        return None
    rule = rules[rule_index]
    if not isinstance(rule, dict):
        return None
    rule_id = rule.get("id")
    return rule_id if isinstance(rule_id, str) else None


def _format_validation_error(exc: ValidationError, raw: bytes | None) -> str:
    parsed: Any = None
    if raw is not None:
        try:
            parsed = yaml.safe_load(raw)
        except yaml.YAMLError:
            parsed = None

    lines: list[str] = []
    for err in exc.errors():
        loc = err["loc"]
        loc_str = ".".join(str(part) for part in loc)
        rule_id = _resolve_rule_id(parsed, loc)
        prefix = f"rule {rule_id!r} ({loc_str})" if rule_id is not None else loc_str
        lines.append(f"  {prefix}: {err['msg']}")
    return "validation errors:\n" + "\n".join(lines)


class CommandRulesValidate:
    """Statically validate issuers.yml rule blocks via the existing loader."""

    def run(self, issuers_path: Path) -> CommandResult:
        if not issuers_path.is_file():
            return CommandResult(success=False, error=f"issuers file not found: {issuers_path}")

        # Read the raw file once so per-error formatting can resolve rule
        # indices to rule ids without re-reading. ``load_registry`` re-reads
        # internally; the cost is negligible.
        try:
            raw = issuers_path.read_bytes()
        except OSError as exc:
            return CommandResult(success=False, error=str(exc))

        try:
            registry = load_registry(issuers_path)
        except ValidationError as exc:
            return CommandResult(success=False, error=_format_validation_error(exc, raw))
        except yaml.YAMLError as exc:
            # Malformed YAML (unclosed flow seq, bad indent, etc.) escapes
            # ``yaml.safe_load`` as YAMLError. Surface it as a CommandResult
            # so the CLI handler routes it through the buvis console rather
            # than crashing with a parser stack trace.
            return CommandResult(success=False, error=f"yaml parse error: {exc}")
        except (RuntimeError, ValueError) as exc:
            return CommandResult(success=False, error=str(exc))

        rule_count = sum(len(entry.rules) for entry in registry.issuers.values())
        issuer_count = len(registry.issuers)
        return CommandResult(
            success=True,
            output=f"OK. Loaded {rule_count} rule(s) across {issuer_count} issuer(s).",
        )
