"""Static rule-engine audit checks.

Pure functions that surface registry-loadability failures, priority
conflicts between enabled rules, and rule-freshness gaps. No I/O beyond
reading the issuers.yml path passed in.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from bim.commands.doc.audit.models import RuleFinding, RuleFindingCode
from bim.commands.doc.shared.issuers import IssuerRegistry, load_registry
from bim.commands.doc.shared.rules.models import ExtractSpec, Rule

__all__ = [
    "check_priority_conflicts",
    "check_registry_loadable",
    "check_rule_freshness",
]


def _resolve_rule_id_from_loc(parsed: Any, loc: tuple[Any, ...]) -> str | None:
    """Walk parsed YAML by the validation-error path; return the rule id
    if the path lands inside a rule. Replicated from rules.validate to
    avoid importing `_`-prefixed internals.
    """
    if not (
        len(loc) >= 4
        and loc[0] == "issuers"
        and isinstance(loc[1], str)
        and loc[2] == "rules"
        and isinstance(loc[3], int)
        and isinstance(parsed, dict)
    ):
        return None
    issuer_body = (parsed.get("issuers") or {}).get(loc[1])
    if not isinstance(issuer_body, dict):
        return None
    rules = issuer_body.get("rules")
    if not isinstance(rules, list) or not (0 <= loc[3] < len(rules)):
        return None
    rule = rules[loc[3]]
    rule_id = rule.get("id") if isinstance(rule, dict) else None
    return rule_id if isinstance(rule_id, str) else None


def _classify_validation_error(msg: str) -> RuleFindingCode:
    if "invalid regex" in msg:
        return "regex_compile_failure"
    if "duplicate rule id" in msg:
        return "duplicate_id"
    return "validation_error"


def check_registry_loadable(
    issuers_path: Path,
) -> tuple[IssuerRegistry | None, list[RuleFinding]]:
    """Load the registry, surfacing all failure modes as RuleFinding entries.

    Returns ``(registry, [])`` on success or ``(None, [findings...])`` on
    failure.
    """
    if not issuers_path.is_file():
        return None, [
            RuleFinding(
                rule_id=None,
                code="validation_error",
                detail=f"issuers file not found: {issuers_path}",
            )
        ]

    try:
        raw = issuers_path.read_bytes()
    except OSError as exc:
        return None, [RuleFinding(rule_id=None, code="validation_error", detail=str(exc))]

    try:
        registry = load_registry(issuers_path)
    except yaml.YAMLError as exc:
        return None, [
            RuleFinding(
                rule_id=None,
                code="validation_error",
                detail=f"yaml parse error: {exc}",
            )
        ]
    except ValidationError as exc:
        parsed: Any = None
        try:
            parsed = yaml.safe_load(raw)
        except yaml.YAMLError:
            parsed = None
        findings: list[RuleFinding] = []
        for err in exc.errors():
            loc = err["loc"]
            loc_str = ".".join(str(part) for part in loc)
            rule_id = _resolve_rule_id_from_loc(parsed, loc)
            code = _classify_validation_error(err["msg"])
            findings.append(
                RuleFinding(
                    rule_id=rule_id,
                    code=code,
                    detail=f"{loc_str}: {err['msg']}",
                )
            )
        return None, findings
    except (ValueError, RuntimeError) as exc:
        msg = str(exc)
        ve_code: RuleFindingCode = "duplicate_id" if "duplicate rule id" in msg else "validation_error"
        return None, [RuleFinding(rule_id=None, code=ve_code, detail=msg)]

    return registry, []


def _pinned_constants(rule: Rule) -> dict[str, str | int | float]:
    """Return the rule's pinned-constant extract entries.

    Only ``str``/``int``/``float`` values are returned; ``ExtractSpec``
    values are skipped because they pull from OCR text at runtime, so
    static disagreement is undecidable.
    """
    constants: dict[str, str | int | float] = {}
    for field, value in rule.extract.items():
        if isinstance(value, ExtractSpec):
            continue
        if isinstance(value, str | int | float):
            constants[field] = value
    return constants


def check_priority_conflicts(registry: IssuerRegistry) -> list[RuleFinding]:
    """Detect pairs of enabled rules sharing a priority that pin the same field
    to statically-different *constant* values.

    LIMITATION: spec wording is "no two enabled rules with same priority and
    overlapping match clauses" -- full match-clause overlap is undecidable
    for arbitrary regexes. We implement the decidable subset: same priority
    plus statically-disagreeing pinned constant values, which is the runtime
    failure mode ``engine._has_pinned_disagreement`` would surface.

    Only constants are compared (str/int/float values in ``extract``).
    Pinned ``ExtractSpec`` values are skipped because they extract from OCR
    text at runtime; disagreement is undecidable without input text.
    """
    enabled_rules: list[Rule] = []
    for entry in registry.issuers.values():
        for rule in entry.rules:
            if rule.enabled:
                enabled_rules.append(rule)

    by_priority: dict[int, list[Rule]] = {}
    for rule in enabled_rules:
        by_priority.setdefault(rule.priority, []).append(rule)

    seen: set[tuple[str, str, str]] = set()
    findings: list[RuleFinding] = []
    for priority, rules in by_priority.items():
        if len(rules) < 2:
            continue
        for rule_a, rule_b in combinations(rules, 2):
            findings.extend(_pair_conflict_findings(rule_a, rule_b, priority, seen))
    return findings


def _pair_conflict_findings(
    rule_a: Rule,
    rule_b: Rule,
    priority: int,
    seen: set[tuple[str, str, str]],
) -> list[RuleFinding]:
    """Emit one priority_conflict finding per shared field with disagreeing constants."""
    if rule_a.id == rule_b.id:
        return []
    consts_a = _pinned_constants(rule_a)
    consts_b = _pinned_constants(rule_b)
    shared_fields = set(consts_a) & set(consts_b)
    findings: list[RuleFinding] = []
    for field in sorted(shared_fields):
        value_a = consts_a[field]
        value_b = consts_b[field]
        if value_a == value_b:
            continue
        first_id, second_id = sorted((rule_a.id, rule_b.id))
        key = (first_id, second_id, field)
        if key in seen:
            continue
        seen.add(key)
        first_value, second_value = (value_a, value_b) if rule_a.id == first_id else (value_b, value_a)
        findings.append(
            RuleFinding(
                rule_id=first_id,
                code="priority_conflict",
                detail=(
                    f"conflicts with rule {second_id!r} at "
                    f"priority {priority} on field {field!r}: "
                    f"{first_value!r} vs {second_value!r}"
                ),
            )
        )
    return findings


def _ensure_utc(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC; pass through aware datetimes unchanged."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def check_rule_freshness(
    registry: IssuerRegistry,
    last_matches: dict[str, datetime],
    now: datetime,
    max_age_days: int = 90,
) -> list[RuleFinding]:
    """Emit a stale_rule finding for every enabled rule with no match in
    the last ``max_age_days`` days. Warning-only; never fails the audit.

    Both ``now`` and the values in ``last_matches`` should be timezone-aware
    UTC. Naive datetimes are pragmatically treated as UTC.
    """
    now_utc = _ensure_utc(now)
    findings: list[RuleFinding] = []
    for entry in registry.issuers.values():
        for rule in entry.rules:
            if not rule.enabled:
                continue
            last = last_matches.get(rule.id)
            if last is None:
                findings.append(
                    RuleFinding(
                        rule_id=rule.id,
                        code="stale_rule",
                        detail="last match: never",
                    )
                )
                continue
            age_days = (now_utc - _ensure_utc(last)).days
            if age_days > max_age_days:
                findings.append(
                    RuleFinding(
                        rule_id=rule.id,
                        code="stale_rule",
                        detail=f"last match: {age_days} days ago",
                    )
                )
    return findings
