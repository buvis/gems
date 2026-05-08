from __future__ import annotations

from .rules_engine_helpers import (
    _CEZ_OCR,
    IssuerRegistry,
    RuleEngine,
    _cez_full_rule,
    _cez_partial_rule,
    _registry,
    _source,
)

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
