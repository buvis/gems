"""Unit tests for the rule-engine audit check functions.

Each check is pure: no console I/O, no file mutation. They return lists
of ``RuleFinding`` (empty list = clean).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from bim.commands.doc.audit.rules_checks import (
    check_priority_conflicts,
    check_registry_loadable,
    check_rule_freshness,
)
from bim.commands.doc.shared.issuers import IssuerEntry, IssuerRegistry
from bim.commands.doc.shared.rules.models import ExtractSpec, MatchClauses, Rule


def _write(path: Path, body: str) -> None:
    path.write_text(body)


def _make_rule(
    rule_id: str,
    *,
    priority: int = 50,
    enabled: bool = True,
    extract: dict | None = None,
    match: MatchClauses | None = None,
) -> Rule:
    return Rule(
        id=rule_id,
        priority=priority,
        enabled=enabled,
        match=match or MatchClauses(ocr_contains=["foo"]),
        extract=extract if extract is not None else {"doc_type": "invoice"},
    )


def _make_registry(rules_by_issuer: dict[str, list[Rule]]) -> IssuerRegistry:
    issuers = {slug: IssuerEntry(slug=slug, display_name=slug, rules=rules) for slug, rules in rules_by_issuer.items()}
    return IssuerRegistry(
        version=1,
        doc_types=["invoice", "statement"],
        reserved_slugs=[],
        issuers=issuers,
    )


class TestCheckRegistryLoadable:
    def test_missing_file_returns_validation_error(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.yml"
        registry, findings = check_registry_loadable(path)
        assert registry is None
        assert len(findings) == 1
        assert findings[0].code == "validation_error"
        assert "not found" in findings[0].detail

    def test_malformed_yaml_returns_validation_error(self, tmp_path: Path) -> None:
        path = tmp_path / "issuers.yml"
        _write(path, ": not yaml :")
        registry, findings = check_registry_loadable(path)
        assert registry is None
        assert len(findings) == 1
        assert findings[0].code == "validation_error"
        assert "yaml parse" in findings[0].detail.lower()

    def test_validation_error_for_unknown_field(self, tmp_path: Path) -> None:
        path = tmp_path / "issuers.yml"
        _write(
            path,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  acme:
    display_name: Acme
    rules:
      - id: acme-1
        bogus: 1
        match: {ocr_contains: ["foo"]}
        extract: {doc_type: invoice}
""",
        )
        registry, findings = check_registry_loadable(path)
        assert registry is None
        assert len(findings) >= 1
        codes = {f.code for f in findings}
        assert "validation_error" in codes
        rule_findings = [f for f in findings if f.rule_id == "acme-1"]
        assert rule_findings, f"expected rule_id 'acme-1' to be resolved, got {findings}"

    def test_invalid_regex_emits_regex_compile_failure(self, tmp_path: Path) -> None:
        path = tmp_path / "issuers.yml"
        _write(
            path,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  acme:
    display_name: Acme
    rules:
      - id: acme-1
        match: {ocr_matches: ["[invalid("]}
        extract: {doc_type: invoice}
""",
        )
        registry, findings = check_registry_loadable(path)
        assert registry is None
        regex_findings = [f for f in findings if f.code == "regex_compile_failure"]
        assert regex_findings, f"expected regex_compile_failure, got {findings}"

    def test_duplicate_rule_id_emits_duplicate_id(self, tmp_path: Path) -> None:
        path = tmp_path / "issuers.yml"
        _write(
            path,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  acme:
    display_name: Acme
    rules:
      - id: dup-1
        match: {ocr_contains: ["foo"]}
        extract: {doc_type: invoice}
  beta:
    display_name: Beta
    rules:
      - id: dup-1
        match: {ocr_contains: ["bar"]}
        extract: {doc_type: invoice}
""",
        )
        registry, findings = check_registry_loadable(path)
        assert registry is None
        assert any(f.code == "duplicate_id" for f in findings), findings
        dup_finding = next(f for f in findings if f.code == "duplicate_id")
        assert "dup-1" in dup_finding.detail

    def test_valid_registry_returns_no_findings(self, tmp_path: Path) -> None:
        path = tmp_path / "issuers.yml"
        _write(
            path,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  acme:
    display_name: Acme
    rules:
      - id: acme-1
        match: {ocr_contains: ["foo"]}
        extract: {doc_type: invoice}
""",
        )
        registry, findings = check_registry_loadable(path)
        assert findings == []
        assert registry is not None
        assert "acme" in registry.issuers


class TestCheckPriorityConflicts:
    def test_no_conflicts_when_priorities_differ(self) -> None:
        registry = _make_registry(
            {
                "acme": [_make_rule("r1", priority=50, extract={"doc_type": "invoice"})],
                "beta": [_make_rule("r2", priority=60, extract={"doc_type": "statement"})],
            }
        )
        assert check_priority_conflicts(registry) == []

    def test_conflict_when_same_priority_disagreeing_field(self) -> None:
        registry = _make_registry(
            {
                "acme": [_make_rule("a-rule", priority=50, extract={"doc_type": "invoice"})],
                "beta": [_make_rule("b-rule", priority=50, extract={"doc_type": "statement"})],
            }
        )
        findings = check_priority_conflicts(registry)
        assert len(findings) == 1
        f = findings[0]
        assert f.code == "priority_conflict"
        assert f.rule_id == "a-rule"
        assert "b-rule" in f.detail
        assert "overlapping match clauses" in f.detail
        assert "doc_type" in f.detail
        assert "invoice" in f.detail
        assert "statement" in f.detail

    def test_conflict_when_same_priority_no_disagreement_overlapping_clauses(self) -> None:
        registry = _make_registry(
            {
                "acme": [_make_rule("a", priority=50, extract={"doc_type": "invoice"})],
                "beta": [_make_rule("b", priority=50, extract={"doc_type": "invoice"})],
            }
        )
        findings = check_priority_conflicts(registry)
        assert len(findings) == 1
        f = findings[0]
        assert f.code == "priority_conflict"
        assert "overlapping match clauses" in f.detail
        # No disagreement enrichment when extract values agree.
        assert "e.g." not in f.detail

    def test_no_conflict_when_disabled_rule(self) -> None:
        registry = _make_registry(
            {
                "acme": [_make_rule("a", priority=50, extract={"doc_type": "invoice"})],
                "beta": [
                    _make_rule(
                        "b",
                        priority=50,
                        enabled=False,
                        extract={"doc_type": "statement"},
                    )
                ],
            }
        )
        assert check_priority_conflicts(registry) == []

    def test_extractspec_does_not_block_overlap_finding(self) -> None:
        spec = ExtractSpec(**{"from": "ocr_match", "pattern": r"(\d+)", "group": 1})
        registry = _make_registry(
            {
                "acme": [_make_rule("a", priority=50, extract={"doc_number": spec})],
                "beta": [
                    _make_rule(
                        "b",
                        priority=50,
                        extract={"doc_number": "constant-string"},
                    )
                ],
            }
        )
        findings = check_priority_conflicts(registry)
        # Both default to ocr_contains=["foo"] so match clauses still overlap.
        assert len(findings) == 1
        assert findings[0].code == "priority_conflict"
        assert "overlapping match clauses" in findings[0].detail
        # ExtractSpec values are skipped from disagreement enrichment.
        assert "e.g." not in findings[0].detail

    def test_one_finding_per_overlapping_pair_with_disagreement_enrichment(self) -> None:
        registry = _make_registry(
            {
                "acme": [
                    _make_rule(
                        "a",
                        priority=50,
                        extract={"doc_type": "invoice", "doc_number": "AAA"},
                    )
                ],
                "beta": [
                    _make_rule(
                        "b",
                        priority=50,
                        extract={"doc_type": "statement", "doc_number": "BBB"},
                    )
                ],
            }
        )
        findings = check_priority_conflicts(registry)
        # New semantics: one finding per overlapping pair, not per shared field.
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "a"
        assert f.code == "priority_conflict"
        assert "overlapping match clauses" in f.detail
        # Disagreement enrichment lists every disagreeing shared field, joined
        # with `; `. Asserting both must be present catches regressions where
        # `_disagreement_enrichment` silently drops a field.
        assert "e.g." in f.detail
        assert "doc_type" in f.detail
        assert "doc_number" in f.detail

    def test_disjoint_email_from_domain_blocks_overlap(self) -> None:
        registry = _make_registry(
            {
                "acme": [
                    _make_rule(
                        "a",
                        priority=50,
                        match=MatchClauses(email_from_domain=["acme.com"]),
                    )
                ],
                "beta": [
                    _make_rule(
                        "b",
                        priority=50,
                        match=MatchClauses(email_from_domain=["beta.com"]),
                    )
                ],
            }
        )
        assert check_priority_conflicts(registry) == []

    def test_intersecting_email_from_domain_keeps_overlap(self) -> None:
        registry = _make_registry(
            {
                "acme": [
                    _make_rule(
                        "a",
                        priority=50,
                        match=MatchClauses(email_from_domain=["acme.com", "beta.com"]),
                    )
                ],
                "beta": [
                    _make_rule(
                        "b",
                        priority=50,
                        match=MatchClauses(email_from_domain=["beta.com", "gamma.com"]),
                    )
                ],
            }
        )
        findings = check_priority_conflicts(registry)
        assert len(findings) == 1
        assert "overlapping match clauses" in findings[0].detail

    def test_case_insensitive_email_from_domain_overlaps(self) -> None:
        # The matcher casefolds both sides at runtime, so literal lists with
        # different casing match the same emails. The audit must treat them
        # as overlapping.
        registry = _make_registry(
            {
                "acme": [
                    _make_rule(
                        "a",
                        priority=50,
                        match=MatchClauses(email_from_domain=["Example.com"]),
                    )
                ],
                "beta": [
                    _make_rule(
                        "b",
                        priority=50,
                        match=MatchClauses(email_from_domain=["example.COM"]),
                    )
                ],
            }
        )
        findings = check_priority_conflicts(registry)
        assert len(findings) == 1
        assert "overlapping match clauses" in findings[0].detail

    def test_suffix_email_from_domain_overlaps(self) -> None:
        # Runtime matcher uses ``domain.endswith(candidate)``, so
        # ``billing.example.com`` matches both ``example.com`` and
        # ``billing.example.com``. Same-priority pair must be flagged.
        registry = _make_registry(
            {
                "acme": [
                    _make_rule(
                        "a",
                        priority=50,
                        match=MatchClauses(email_from_domain=["example.com"]),
                    )
                ],
                "beta": [
                    _make_rule(
                        "b",
                        priority=50,
                        match=MatchClauses(email_from_domain=["billing.example.com"]),
                    )
                ],
            }
        )
        findings = check_priority_conflicts(registry)
        assert len(findings) == 1
        assert "overlapping match clauses" in findings[0].detail

    def test_unrelated_subdomains_email_from_domain_disjoint(self) -> None:
        # ``billing.example.com`` and ``mail.example.com`` are not suffixes
        # of each other and no domain ends with both, so they remain disjoint.
        registry = _make_registry(
            {
                "acme": [
                    _make_rule(
                        "a",
                        priority=50,
                        match=MatchClauses(email_from_domain=["billing.example.com"]),
                    )
                ],
                "beta": [
                    _make_rule(
                        "b",
                        priority=50,
                        match=MatchClauses(email_from_domain=["mail.example.com"]),
                    )
                ],
            }
        )
        assert check_priority_conflicts(registry) == []

    def test_one_side_unconstrained_email_domain_overlaps(self) -> None:
        registry = _make_registry(
            {
                "acme": [
                    _make_rule(
                        "a",
                        priority=50,
                        match=MatchClauses(email_from_domain=["acme.com"]),
                    )
                ],
                "beta": [_make_rule("b", priority=50)],
            }
        )
        findings = check_priority_conflicts(registry)
        assert len(findings) == 1
        assert "overlapping match clauses" in findings[0].detail


class TestCheckRuleFreshness:
    def test_never_matched_emits_stale(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        registry = _make_registry({"acme": [_make_rule("r1")]})
        findings = check_rule_freshness(registry, last_matches={}, now=now)
        assert len(findings) == 1
        assert findings[0].code == "stale_rule"
        assert findings[0].rule_id == "r1"
        assert "never" in findings[0].detail

    def test_recent_match_no_finding(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        registry = _make_registry({"acme": [_make_rule("r1")]})
        last = {"r1": now - timedelta(days=30)}
        findings = check_rule_freshness(registry, last_matches=last, now=now)
        assert findings == []

    def test_old_match_emits_stale_with_age(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        registry = _make_registry({"acme": [_make_rule("r1")]})
        last = {"r1": now - timedelta(days=100)}
        findings = check_rule_freshness(registry, last_matches=last, now=now)
        assert len(findings) == 1
        assert findings[0].code == "stale_rule"
        assert findings[0].rule_id == "r1"
        assert "100 days" in findings[0].detail

    def test_disabled_rule_skipped(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        registry = _make_registry({"acme": [_make_rule("r1", enabled=False)]})
        findings = check_rule_freshness(registry, last_matches={}, now=now)
        assert findings == []

    def test_custom_max_age(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        registry = _make_registry({"acme": [_make_rule("r1")]})
        last = {"r1": now - timedelta(days=31)}
        findings = check_rule_freshness(registry, last_matches=last, now=now, max_age_days=30)
        assert len(findings) == 1
        assert findings[0].code == "stale_rule"
