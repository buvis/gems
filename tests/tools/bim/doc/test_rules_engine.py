"""Tests for the rule engine orchestrator in ``bim.commands.doc.shared.rules.engine``.

These tests are the spec for the to-be-implemented rule engine. They will fail
with ``ImportError`` until the implementation lands; that is expected.

Assumptions made where the spec was ambiguous:

- ``RuleEngine`` is stateless — its constructor takes no args and the same
  instance can be reused for many ``evaluate`` calls without leaking state.
- ``RuleEngine.evaluate`` returns a fresh ``RuleResult`` for every call. On
  ``kind="none"``, ``pinned`` is empty, ``rule_id`` and ``rule_version`` are
  ``None``, and ``conflicting_rules`` is empty.
- "Full beats partial" applies even when the partial rule has a strictly
  higher ``priority`` than the full rule. Full-vs-partial is decided before
  priority is consulted.
- "File order" tiebreak among rules of the SAME issuer is the order of
  ``IssuerEntry.rules`` (the list as built by the YAML loader). When the
  engine has to break a tie among rules from DIFFERENT issuers, the order is
  the iteration order of ``IssuerRegistry.issuers`` (a dict, which on Python
  3.7+ preserves insertion order — and ``IssuerRegistry.model_validate`` on a
  plain dict reflects that input order).
- "Conflict" requires DISAGREEMENT on the pinned ``issuer_slug``. Two rules
  pinning the SAME ``issuer_slug`` (or both rules omitting ``issuer_slug``
  but agreeing on every shared key) are NOT a conflict — file order breaks
  the tie. The PRD's wording "disagreeing on ``issuer_slug``" is taken
  literally for the v1 conflict signal.
- ``conflicting_rules`` lists every rule id that participated in the
  unresolved tie, not just two. The list order is deterministic; for the
  purposes of these tests we only assert on the SET of ids unless order is
  meaningful.
- A rule whose match clauses pass but whose ``apply_extract`` returns
  ``None`` (e.g. transform failure) contributes NOTHING — neither a result
  nor a conflict. The engine moves on as if that rule had not matched.
- Disabled rules (``enabled=False``) are skipped entirely: never matched,
  never extracted, never counted toward conflicts.
- ``scoped_issuer_slug`` is an exact slug (not an alias). Rules belonging to
  any other issuer are skipped. Reserved or unknown slugs cause every rule
  to be skipped (yielding ``kind="none"``); they do not raise.
"""

from __future__ import annotations

from typing import Any

from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.rules.engine import RuleEngine
from bim.commands.doc.shared.rules.models import RuleResult, SourceMetadata

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source(
    *,
    source_kind: str = "filesystem",
    original_filename: str | None = None,
    email_from: str | None = None,
    email_subject: str | None = None,
    email_date: str | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        source_kind=source_kind,
        original_filename=original_filename,
        email_from=email_from,
        email_subject=email_subject,
        email_date=email_date,
    )


def _registry(issuers: dict[str, dict[str, Any]]) -> IssuerRegistry:
    """Build an ``IssuerRegistry`` from a compact dict, filling stable defaults."""
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": ["invoice", "receipt", "statement", "other"],
            "reserved_slugs": ["unknown", "_triage", "_config"],
            "issuers": issuers,
        }
    )


def _empty_registry() -> IssuerRegistry:
    return _registry({})


def _cez_full_rule(*, rule_id: str = "cez-invoice-2024-template", priority: int = 100) -> dict[str, Any]:
    return {
        "id": rule_id,
        "version": 1,
        "priority": priority,
        "match": {
            "ocr_contains": ["IC: 45274649", "Faktura"],
            "ocr_matches": [r"Faktura č\.\s*(\d{10})"],
        },
        "extract": {
            "doc_type": "invoice",
            "doc_number": {
                "from": "ocr_match",
                "pattern": r"Faktura č\.\s*(\d{10})",
                "group": 1,
            },
            "doc_currency": "CZK",
            "doc_language": "cs",
        },
    }


def _cez_partial_rule(*, rule_id: str = "cez-fingerprint", priority: int = 50) -> dict[str, Any]:
    return {
        "id": rule_id,
        "version": 1,
        "priority": priority,
        "partial": True,
        "match": {
            "ocr_contains": ["IC: 45274649"],
        },
        "extract": {
            "issuer_slug": "cez-as",
            "issuer_display": "CEZ a.s.",
            "doc_language": "cs",
        },
    }


_CEZ_OCR = "Dodavatel: CEZ a.s.\nIC: 45274649\nFaktura č. 1234567890\nDatum vystaveni: 01.06.2024\n"


# ---------------------------------------------------------------------------
# Empty registry
# ---------------------------------------------------------------------------


class TestEmptyRegistry:
    def test_no_issuers_returns_kind_none(self) -> None:
        engine = RuleEngine()
        registry = _empty_registry()

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert isinstance(result, RuleResult)
        assert result.kind == "none"
        assert result.pinned == {}
        assert result.rule_id is None
        assert result.rule_version is None
        assert result.conflicting_rules == []

    def test_issuer_with_no_rules_returns_kind_none(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "none"
        assert result.pinned == {}
        assert result.rule_id is None
        assert result.rule_version is None


# ---------------------------------------------------------------------------
# Single rule outcomes
# ---------------------------------------------------------------------------


class TestSingleFullRule:
    def test_match_returns_kind_full_with_pinned_dict(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [_cez_full_rule()],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "full"
        assert result.rule_id == "cez-invoice-2024-template"
        assert result.rule_version == 1
        assert result.pinned["doc_type"] == "invoice"
        assert result.pinned["doc_number"] == "1234567890"
        assert result.pinned["doc_currency"] == "CZK"
        assert result.pinned["doc_language"] == "cs"
        assert result.conflicting_rules == []


class TestSinglePartialRule:
    def test_match_returns_kind_partial_with_pinned_dict(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [_cez_partial_rule()],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "cez-fingerprint"
        assert result.rule_version == 1
        assert result.pinned["issuer_slug"] == "cez-as"
        assert result.pinned["issuer_display"] == "CEZ a.s."
        assert result.pinned["doc_language"] == "cs"
        assert result.conflicting_rules == []


class TestNoRuleMatches:
    def test_rules_present_but_none_match_returns_kind_none(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [_cez_full_rule(), _cez_partial_rule()],
                },
            }
        )

        # OCR text without the CEZ fingerprint.
        result = engine.evaluate("Receipt from grocery store. No issuer signature.", _source(), registry)

        assert result.kind == "none"
        assert result.pinned == {}
        assert result.rule_id is None
        assert result.rule_version is None


# ---------------------------------------------------------------------------
# Full beats partial
# ---------------------------------------------------------------------------


class TestFullBeatsPartial:
    def test_full_wins_over_partial_when_both_match(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [_cez_full_rule(), _cez_partial_rule()],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "full"
        assert result.rule_id == "cez-invoice-2024-template"

    def test_full_wins_even_when_partial_has_higher_priority(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [
                        _cez_full_rule(priority=10),
                        _cez_partial_rule(priority=999),
                    ],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "full"
        assert result.rule_id == "cez-invoice-2024-template"


# ---------------------------------------------------------------------------
# Higher priority wins (within same partial-ness)
# ---------------------------------------------------------------------------


class TestPriorityWins:
    def test_higher_priority_full_rule_wins(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [
                        _cez_full_rule(rule_id="cez-low", priority=50),
                        _cez_full_rule(rule_id="cez-high", priority=100),
                    ],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "full"
        assert result.rule_id == "cez-high"

    def test_higher_priority_partial_rule_wins(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [
                        _cez_partial_rule(rule_id="cez-fp-low", priority=10),
                        _cez_partial_rule(rule_id="cez-fp-high", priority=200),
                    ],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "cez-fp-high"


# ---------------------------------------------------------------------------
# File-order tiebreak (equal priority, agreement)
# ---------------------------------------------------------------------------


class TestFileOrderTiebreak:
    def test_first_in_issuer_rules_list_wins_when_priority_equal_and_agree(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [
                        _cez_full_rule(rule_id="cez-first", priority=50),
                        _cez_full_rule(rule_id="cez-second", priority=50),
                    ],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "full"
        assert result.rule_id == "cez-first"

    def test_first_in_issuer_rules_list_wins_for_partials(self) -> None:
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [
                        _cez_partial_rule(rule_id="cez-fp-first", priority=50),
                        _cez_partial_rule(rule_id="cez-fp-second", priority=50),
                    ],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "cez-fp-first"

    def test_first_listed_issuer_wins_when_rules_belong_to_different_issuers_and_agree(self) -> None:
        """Two partial rules from different issuers, equal priority, both pin the same issuer_slug.

        Same-partial-ness, equal priority, no disagreement → file order resolves the tie.
        First-listed issuer in the registry wins.
        """
        engine = RuleEngine()
        # Both rules pin issuer_slug=cez-as (agreement). Issuer "cez-as" listed first.
        rule_a = _cez_partial_rule(rule_id="rule-a", priority=50)
        rule_b = _cez_partial_rule(rule_id="rule-b", priority=50)
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_a],
                },
                "other-issuer": {
                    "slug": "other-issuer",
                    "display_name": "Other Issuer",
                    "rules": [rule_b],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "rule-a"


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


class TestConflict:
    def test_two_partial_rules_disagree_on_issuer_slug(self) -> None:
        engine = RuleEngine()
        # Two partial rules with the SAME generic match clause but DIFFERENT issuer_slug.
        rule_a = {
            "id": "rule-cez",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "issuer_slug": "cez-as",
                "issuer_display": "CEZ a.s.",
            },
        }
        rule_b = {
            "id": "rule-eon",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "issuer_slug": "eon-cz",
                "issuer_display": "E.ON Czech",
            },
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_a],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [rule_b],
                },
            }
        )

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        assert result.kind == "conflict"
        assert set(result.conflicting_rules) == {"rule-cez", "rule-eon"}
        # On conflict no rule "wins" — pinned/rule_id semantics:
        assert result.pinned == {}
        assert result.rule_id is None
        assert result.rule_version is None

    def test_two_full_rules_disagree_on_issuer_slug(self) -> None:
        engine = RuleEngine()
        rule_a = {
            "id": "full-cez",
            "version": 1,
            "priority": 50,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "doc_type": "invoice",
                "issuer_slug": "cez-as",
            },
        }
        rule_b = {
            "id": "full-eon",
            "version": 1,
            "priority": 50,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "doc_type": "invoice",
                "issuer_slug": "eon-cz",
            },
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_a],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [rule_b],
                },
            }
        )

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        assert result.kind == "conflict"
        assert set(result.conflicting_rules) == {"full-cez", "full-eon"}

    def test_conflict_only_among_same_partial_ness(self) -> None:
        """A full rule and a partial rule that pin different issuer_slug should NOT conflict.

        Full beats partial outright; the partial is suppressed before conflict resolution.
        """
        engine = RuleEngine()
        full_rule = {
            "id": "full-cez",
            "version": 1,
            "priority": 50,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "doc_type": "invoice",
                "issuer_slug": "cez-as",
            },
        }
        partial_rule = {
            "id": "partial-eon",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "issuer_slug": "eon-cz",
            },
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [full_rule],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [partial_rule],
                },
            }
        )

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        assert result.kind == "full"
        assert result.rule_id == "full-cez"
        assert result.conflicting_rules == []

    def test_higher_priority_breaks_potential_conflict(self) -> None:
        """Two rules disagree on issuer_slug, but one has higher priority.

        Conflict resolution only fires when priority is also tied.
        """
        engine = RuleEngine()
        rule_a = {
            "id": "rule-cez",
            "version": 1,
            "priority": 100,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"issuer_slug": "cez-as"},
        }
        rule_b = {
            "id": "rule-eon",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"issuer_slug": "eon-cz"},
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_a],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [rule_b],
                },
            }
        )

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "rule-cez"
        assert result.conflicting_rules == []


# ---------------------------------------------------------------------------
# Disabled rules
# ---------------------------------------------------------------------------


class TestDisabledRules:
    def test_disabled_rule_skipped_even_if_it_would_match(self) -> None:
        engine = RuleEngine()
        disabled_full = dict(_cez_full_rule())
        disabled_full["enabled"] = False
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [disabled_full],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "none"
        assert result.rule_id is None

    def test_disabled_full_rule_does_not_suppress_partial(self) -> None:
        """Disabled full rule must NOT trigger 'full beats partial' suppression."""
        engine = RuleEngine()
        disabled_full = dict(_cez_full_rule())
        disabled_full["enabled"] = False
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [disabled_full, _cez_partial_rule()],
                },
            }
        )

        result = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "cez-fingerprint"

    def test_disabled_rule_does_not_count_toward_conflict(self) -> None:
        engine = RuleEngine()
        rule_active = {
            "id": "rule-cez",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"issuer_slug": "cez-as"},
        }
        rule_disabled = {
            "id": "rule-eon",
            "version": 1,
            "priority": 50,
            "enabled": False,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"issuer_slug": "eon-cz"},
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_active],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [rule_disabled],
                },
            }
        )

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "rule-cez"
        assert result.conflicting_rules == []


# ---------------------------------------------------------------------------
# Source-scoped issuer
# ---------------------------------------------------------------------------


class TestScopedIssuer:
    def _two_issuer_registry(self) -> IssuerRegistry:
        rule_cez = {
            "id": "rule-cez",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"issuer_slug": "cez-as"},
        }
        rule_eon = {
            "id": "rule-eon",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"issuer_slug": "eon-cz"},
        }
        return _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_cez],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [rule_eon],
                },
            }
        )

    def test_scoped_issuer_considers_only_its_rules(self) -> None:
        engine = RuleEngine()
        registry = self._two_issuer_registry()

        result = engine.evaluate(
            "Energy bill summary for the period.",
            _source(),
            registry,
            scoped_issuer_slug="cez-as",
        )

        assert result.kind == "partial"
        assert result.rule_id == "rule-cez"
        assert result.conflicting_rules == []

    def test_scoped_issuer_skips_other_issuers_rules(self) -> None:
        """Only the eon-cz rule would match for that OCR text shape, but we scope to cez-as."""
        engine = RuleEngine()
        # Build a registry where ONLY the eon-cz rule would match.
        rule_eon = {
            "id": "rule-eon",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Faktura za elektrinu"]},
            "extract": {"issuer_slug": "eon-cz"},
        }
        rule_cez = {
            "id": "rule-cez",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Marker that is not in the OCR"]},
            "extract": {"issuer_slug": "cez-as"},
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_cez],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [rule_eon],
                },
            }
        )

        result = engine.evaluate(
            "Faktura za elektrinu z mesica.",
            _source(),
            registry,
            scoped_issuer_slug="cez-as",
        )

        assert result.kind == "none"
        assert result.rule_id is None

    def test_scoped_to_unknown_slug_returns_none(self) -> None:
        engine = RuleEngine()
        registry = self._two_issuer_registry()

        result = engine.evaluate(
            "Energy bill summary for the period.",
            _source(),
            registry,
            scoped_issuer_slug="not-a-real-issuer",
        )

        assert result.kind == "none"
        assert result.rule_id is None

    def test_unscoped_call_considers_all_issuers(self) -> None:
        """Sanity check: without ``scoped_issuer_slug`` both issuer pools are evaluated."""
        engine = RuleEngine()
        registry = self._two_issuer_registry()

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        # Both rules match and disagree → conflict.
        assert result.kind == "conflict"
        assert set(result.conflicting_rules) == {"rule-cez", "rule-eon"}


# ---------------------------------------------------------------------------
# Extract failure
# ---------------------------------------------------------------------------


class TestExtractFailureSkipsRule:
    def test_extract_failure_makes_rule_contribute_nothing(self) -> None:
        """A full rule whose match passes but whose extract fails (transform on bad input)
        is skipped silently. If it was the only matching rule, the engine returns kind=none.
        """
        engine = RuleEngine()
        # Match clause passes (ocr contains "Faktura"), but the extract pattern
        # captures non-numeric text and tries to coerce it to int → transform fails.
        bad_rule = {
            "id": "bad-extract",
            "version": 1,
            "priority": 50,
            "match": {"ocr_contains": ["Faktura"]},
            "extract": {
                "doc_type": "invoice",
                "doc_amount": {
                    "from": "ocr_match",
                    "pattern": r"Total: ([A-Za-z]+)",
                    "group": 1,
                    "transform": "strip_whitespace_to_int",
                },
            },
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [bad_rule],
                },
            }
        )

        ocr = "Faktura\nTotal: notanumber"
        result = engine.evaluate(ocr, _source(), registry)

        assert result.kind == "none"
        assert result.rule_id is None

    def test_extract_failure_lets_lower_priority_rule_win(self) -> None:
        """The high-priority rule's extract fails → engine falls through to the next
        viable rule (a partial here) instead of yielding 'none'."""
        engine = RuleEngine()
        bad_full = {
            "id": "bad-extract",
            "version": 1,
            "priority": 100,
            "match": {"ocr_contains": ["Faktura"]},
            "extract": {
                "doc_type": "invoice",
                "doc_amount": {
                    "from": "ocr_match",
                    "pattern": r"Total: ([A-Za-z]+)",
                    "group": 1,
                    "transform": "strip_whitespace_to_int",
                },
            },
        }
        good_partial = {
            "id": "fingerprint-fallback",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Faktura"]},
            "extract": {
                "issuer_slug": "cez-as",
                "issuer_display": "CEZ a.s.",
            },
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [bad_full, good_partial],
                },
            }
        )

        ocr = "Faktura\nTotal: notanumber"
        result = engine.evaluate(ocr, _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "fingerprint-fallback"
        assert result.pinned["issuer_slug"] == "cez-as"

    def test_extract_failure_does_not_count_toward_conflict(self) -> None:
        """Two same-priority partials disagree, but one's extract fails → the other wins."""
        engine = RuleEngine()
        # This rule's extract has only literal values, so it can't fail.
        rule_good = {
            "id": "rule-cez",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"issuer_slug": "cez-as"},
        }
        # This rule's extract pattern won't capture from the OCR → returns None → skipped.
        rule_bad = {
            "id": "rule-eon",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "issuer_slug": "eon-cz",
                "doc_number": {
                    "from": "ocr_match",
                    "pattern": r"NUMBER-NEVER-IN-TEXT-(\d+)",
                    "group": 1,
                },
            },
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_good],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [rule_bad],
                },
            }
        )

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        assert result.kind == "partial"
        assert result.rule_id == "rule-cez"
        assert result.conflicting_rules == []


# ---------------------------------------------------------------------------
# Engine statelessness
# ---------------------------------------------------------------------------


class TestEngineStateless:
    def test_same_engine_handles_back_to_back_calls(self) -> None:
        """Stateless engine must produce correct results across repeated, varied calls."""
        engine = RuleEngine()
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [_cez_full_rule(), _cez_partial_rule()],
                },
            }
        )

        # Match → full.
        first = engine.evaluate(_CEZ_OCR, _source(), registry)
        # No-match.
        second = engine.evaluate("Unrelated text.", _source(), registry)
        # Match → full again.
        third = engine.evaluate(_CEZ_OCR, _source(), registry)

        assert first.kind == "full"
        assert second.kind == "none"
        assert third.kind == "full"
        assert first.rule_id == third.rule_id == "cez-invoice-2024-template"
