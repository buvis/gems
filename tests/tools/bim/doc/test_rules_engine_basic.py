from __future__ import annotations

from .rules_engine_helpers import (
    _CEZ_OCR,
    RuleEngine,
    RuleResult,
    _cez_full_rule,
    _cez_partial_rule,
    _empty_registry,
    _registry,
    _source,
)

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
