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
from bim.commands.doc.shared.rules.models import ExtractSpec, MatchClauses, Rule

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


# Marker strings emitted by the registry-loading validators. Keeping them
# centralised makes the dependency between this classifier and the validator
# error messages explicit: changing either side without updating the other
# silently mis-classifies findings. Production validators raising these are:
# - ``ExtractSpec._pattern_compiles`` / ``MatchClauses._regex_lists_compile``
#   / ``MatchClauses._filename_regex_compiles`` (via ``_compile_regex``)
#   raise ``ValueError(f"invalid regex {pattern!r}: {exc}")``.
# - ``IssuerRegistry`` rule-id-uniqueness check raises
#   ``ValueError(f"duplicate rule id ...")``.
_INVALID_REGEX_MARKER = "invalid regex"
_DUPLICATE_RULE_ID_MARKER = "duplicate rule id"


def _classify_validation_error(msg: str) -> RuleFindingCode:
    """Map a pydantic ``ValidationError.errors()[i]['msg']`` to a finding code.

    Pydantic v2 wraps ``ValueError`` raised inside field/model validators
    with ``type='value_error'`` and the original message as ``msg``. We
    pattern-match on stable substrings produced by our own validators
    (see ``_INVALID_REGEX_MARKER`` / ``_DUPLICATE_RULE_ID_MARKER``);
    anything else falls back to the generic ``validation_error`` bucket.
    """
    if _INVALID_REGEX_MARKER in msg:
        return "regex_compile_failure"
    if _DUPLICATE_RULE_ID_MARKER in msg:
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
    """Detect pairs of enabled rules sharing a priority whose match clauses
    can both apply to the same document (spec §9 "No conflicts").

    Static-overlap heuristic. Two rules are reported as conflicting iff:

    * they are both enabled,
    * they share the same priority,
    * they share the same ``partial`` flag (``engine._select_winner``
      gives full rules priority over partial rules at any shared priority,
      so cross-flag pairs never collide at runtime), and
    * their ``match`` clauses are not statically provably disjoint.

    The only statically decidable disjointness we detect is on
    ``email_from_domain`` -- when both rules constrain the field with literal
    domain lists and those lists do not intersect, no document can satisfy
    both. All other clause types (``ocr_contains``, regex matchers, filename
    regex, subject substrings) are conservatively treated as potentially
    overlapping; regex/substring disjointness is undecidable in general.

    When both rules pin the same ``extract`` field to statically-different
    constant values, that disagreement is appended to the finding detail to
    help authors locate the source of the conflict. Pinned ``ExtractSpec``
    values are skipped from the disagreement enrichment because they extract
    from OCR text at runtime; static comparison is meaningless.

    One finding is emitted per overlapping pair. ``rule_id`` is the
    lexicographically smaller id of the pair; the detail names the partner.
    """
    enabled_rules: list[Rule] = []
    for entry in registry.issuers.values():
        for rule in entry.rules:
            if rule.enabled:
                enabled_rules.append(rule)

    by_priority: dict[int, list[Rule]] = {}
    for rule in enabled_rules:
        by_priority.setdefault(rule.priority, []).append(rule)

    seen_pairs: set[tuple[str, str]] = set()
    findings: list[RuleFinding] = []
    for priority, rules in by_priority.items():
        if len(rules) < 2:
            continue
        for rule_a, rule_b in combinations(rules, 2):
            finding = _pair_overlap_finding(rule_a, rule_b, priority, seen_pairs)
            if finding is not None:
                findings.append(finding)
    return findings


def _pair_overlap_finding(
    rule_a: Rule,
    rule_b: Rule,
    priority: int,
    seen_pairs: set[tuple[str, str]],
) -> RuleFinding | None:
    """Emit one ``priority_conflict`` finding if the pair's match clauses can overlap."""
    if rule_a.id == rule_b.id:
        return None
    # ``engine._select_winner`` partitions survivors by ``partial``: full
    # rules pre-empt partial rules at any priority, so a same-priority
    # full+partial pair never collides at runtime. Skip it here too.
    if rule_a.partial != rule_b.partial:
        return None
    first_id, second_id = sorted((rule_a.id, rule_b.id))
    key = (first_id, second_id)
    if key in seen_pairs:
        return None
    if not _match_clauses_can_overlap(rule_a.match, rule_b.match):
        return None
    seen_pairs.add(key)
    detail = f"conflicts with rule {second_id!r} at priority {priority}: overlapping match clauses"
    enrichment = _disagreement_enrichment(rule_a, rule_b, first_id)
    if enrichment:
        detail = f"{detail} ({enrichment})"
    return RuleFinding(rule_id=first_id, code="priority_conflict", detail=detail)


def _match_clauses_can_overlap(a: MatchClauses, b: MatchClauses) -> bool:
    """Return True if some document could satisfy both clause sets.

    The only statically decidable disjointness is on ``email_from_domain``.
    The runtime matcher (``_eval_email_from_domain``) casefolds the sender
    domain and uses ``str.endswith`` against each candidate, so two literal
    lists are disjoint iff no candidate from one side is a (case-folded)
    suffix of any candidate from the other side; otherwise some address
    can satisfy both lists. All other clause types (regex, substring) are
    conservatively treated as overlapping. An unconstrained side (None)
    imposes no restriction on that field.
    """
    if a.email_from_domain is not None and b.email_from_domain is not None:
        if not _email_domain_lists_can_overlap(a.email_from_domain, b.email_from_domain):
            return False
    return True


def _email_domain_lists_can_overlap(a: list[str], b: list[str]) -> bool:
    """Return True iff some address can satisfy both literal-domain lists.

    Mirrors the runtime matcher's casefold + suffix semantics: a domain
    ``d`` matches a candidate ``c`` when ``d.endswith(c)``. So lists ``A``
    and ``B`` can overlap iff there exist ``ca`` in A and ``cb`` in B
    such that one is a suffix of the other (case-folded). Equal candidates
    are the trivial case (``ca == cb``).
    """
    folded_a = [candidate.casefold() for candidate in a]
    folded_b = [candidate.casefold() for candidate in b]
    for ca in folded_a:
        for cb in folded_b:
            if ca.endswith(cb) or cb.endswith(ca):
                return True
    return False


def _disagreement_enrichment(
    rule_a: Rule,
    rule_b: Rule,
    first_id: str,
) -> str:
    """Build an `e.g. field <name>: <a> vs <b>` snippet for disagreeing constants.

    Returns an empty string when no shared ``extract`` field has
    statically-different constant values across the two rules.
    """
    consts_a = _pinned_constants(rule_a)
    consts_b = _pinned_constants(rule_b)
    shared_fields = sorted(set(consts_a) & set(consts_b))
    parts: list[str] = []
    for field in shared_fields:
        value_a = consts_a[field]
        value_b = consts_b[field]
        if value_a == value_b:
            continue
        first_value, second_value = (value_a, value_b) if rule_a.id == first_id else (value_b, value_a)
        parts.append(f"field {field!r}: {first_value!r} vs {second_value!r}")
    if not parts:
        return ""
    return "e.g. " + "; ".join(parts)


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
