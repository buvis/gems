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
