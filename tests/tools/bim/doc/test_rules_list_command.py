"""Tests for the bim doc rules list command class."""

from __future__ import annotations

from bim.commands.doc.shared.issuers import IssuerRegistry


def _build_registry(*, with_rules: bool = True, disabled: bool = False) -> IssuerRegistry:
    rules_a = (
        [
            {
                "id": "cez-invoice-2024-template",
                "version": 1,
                "priority": 100,
                "match": {"ocr_contains": ["IC: 45274649"]},
                "extract": {"doc_type": "invoice", "doc_currency": "CZK"},
            },
            {
                "id": "cez-fingerprint",
                "partial": True,
                "match": {"ocr_contains": ["IC: 45274649"]},
                "extract": {"issuer_slug": "cez-as", "issuer_display": "CEZ a.s."},
            },
        ]
        if with_rules
        else []
    )
    rules_b = (
        [
            {
                "id": "eon-invoice-2024",
                "version": 2,
                "priority": 50,
                "enabled": not disabled,
                "match": {"ocr_contains": ["IC: 25733591"]},
                "extract": {"doc_type": "invoice", "doc_currency": "CZK"},
            },
        ]
        if with_rules
        else []
    )
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": ["invoice", "receipt", "statement"],
            "reserved_slugs": ["unknown"],
            "issuers": {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "aliases": [],
                    "rules": rules_a,
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Energie a.s.",
                    "aliases": [],
                    "rules": rules_b,
                },
            },
        }
    )


class TestRulesListCommandEmpty:
    def test_no_rules_anywhere_returns_empty_message(self) -> None:
        from bim.commands.doc.rules.list import CommandRulesList

        registry = _build_registry(with_rules=False)
        result = CommandRulesList().run(registry)
        assert result.success is True
        assert "no rules" in (result.output or "").lower()


class TestRulesListCommandHappy:
    def test_lists_all_rules_with_required_columns(self) -> None:
        from bim.commands.doc.rules.list import CommandRulesList

        registry = _build_registry(with_rules=True)
        result = CommandRulesList().run(registry)
        assert result.success is True
        output = result.output or ""
        assert "cez-invoice-2024-template" in output
        assert "cez-fingerprint" in output
        assert "eon-invoice-2024" in output
        for header in ("id", "issuer", "version", "partial", "priority", "enabled"):
            assert header in output.lower()

    def test_disabled_rule_marked(self) -> None:
        from bim.commands.doc.rules.list import CommandRulesList

        registry = _build_registry(with_rules=True, disabled=True)
        result = CommandRulesList().run(registry)
        assert result.success is True
        output = (result.output or "").lower()
        assert "false" in output or "no" in output or "disabled" in output


class TestRulesListCommandSorted:
    def test_rules_grouped_by_issuer(self) -> None:
        """Rules from cez-as appear before rules from eon-cz."""
        from bim.commands.doc.rules.list import CommandRulesList

        registry = _build_registry(with_rules=True)
        result = CommandRulesList().run(registry)
        output = result.output or ""
        cez_pos = output.find("cez-fingerprint")
        eon_pos = output.find("eon-invoice-2024")
        assert cez_pos != -1 and eon_pos != -1
        assert cez_pos < eon_pos
