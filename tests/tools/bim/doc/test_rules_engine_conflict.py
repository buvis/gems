from __future__ import annotations

from .rules_engine_helpers import (
    _CEZ_OCR,
    RuleEngine,
    _cez_full_rule,
    _cez_partial_rule,
    _registry,
    _source,
)

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

    def test_two_partial_rules_disagree_on_doc_type(self) -> None:
        """Conflict detection covers any pinned field, not just issuer_slug.

        Two same-priority partial rules that pin the same ``issuer_slug``
        but pin different ``doc_type`` values are a conflict: the engine
        cannot pick a winner without losing data.
        """
        engine = RuleEngine()
        rule_invoice = {
            "id": "rule-cez-invoice",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "issuer_slug": "cez-as",
                "doc_type": "invoice",
            },
        }
        rule_statement = {
            "id": "rule-cez-statement",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {
                "issuer_slug": "cez-as",
                "doc_type": "statement",
            },
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_invoice, rule_statement],
                },
            }
        )

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        assert result.kind == "conflict"
        assert set(result.conflicting_rules) == {"rule-cez-invoice", "rule-cez-statement"}
        assert result.rule_id is None

    def test_two_partial_rules_pin_disjoint_fields_do_not_conflict(self) -> None:
        """Pinning non-overlapping fields is not a disagreement.

        Rule A pins only ``issuer_slug``; rule B pins only ``doc_language``.
        No single field has two different values, so neither rule conflicts
        with the other; the engine returns ``kind=partial`` for the picked
        rule and ``conflicting_rules`` stays empty.
        """
        engine = RuleEngine()
        rule_issuer = {
            "id": "rule-issuer",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"issuer_slug": "cez-as"},
        }
        rule_language = {
            "id": "rule-language",
            "version": 1,
            "priority": 50,
            "partial": True,
            "match": {"ocr_contains": ["Energy bill"]},
            "extract": {"doc_language": "cs"},
        }
        registry = _registry(
            {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_issuer, rule_language],
                },
            }
        )

        result = engine.evaluate("Energy bill summary for the period.", _source(), registry)

        assert result.kind == "partial"
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
