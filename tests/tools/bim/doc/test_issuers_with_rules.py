"""Tests for IssuerEntry's new ``rules: list[Rule]`` field and cross-issuer
rule-id uniqueness validation. Companion to ``test_issuers.py`` — does not
modify it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from bim.commands.doc.shared.issuers import IssuerEntry, load_registry
from bim.commands.doc.shared.rules.models import Rule
from pydantic import ValidationError

FIXTURES = Path(__file__).parent / "fixtures" / "issuers"


@pytest.fixture
def with_rules_path(tmp_path: Path) -> Path:
    dest = tmp_path / "issuers.yml"
    shutil.copy(FIXTURES / "with_rules.yml", dest)
    return dest


@pytest.fixture
def with_rules_duplicate_path(tmp_path: Path) -> Path:
    dest = tmp_path / "issuers.yml"
    shutil.copy(FIXTURES / "with_rules_duplicate.yml", dest)
    return dest


@pytest.fixture
def valid_registry_path(tmp_path: Path) -> Path:
    dest = tmp_path / "issuers.yml"
    shutil.copy(FIXTURES / "valid.yml", dest)
    return dest


@pytest.fixture
def aliases_registry_path(tmp_path: Path) -> Path:
    dest = tmp_path / "issuers.yml"
    shutil.copy(FIXTURES / "with_aliases.yml", dest)
    return dest


class TestBackwardCompatibility:
    """Existing fixtures without ``rules:`` blocks must still load and produce
    an empty rules list per issuer.
    """

    def test_valid_yaml_without_rules_loads_with_empty_rules(self, valid_registry_path: Path) -> None:
        registry = load_registry(valid_registry_path)
        assert registry.issuers["cez-as"].rules == []
        assert registry.issuers["plzensky-prazdroj"].rules == []

    def test_with_aliases_yaml_loads_with_empty_rules(self, aliases_registry_path: Path) -> None:
        registry = load_registry(aliases_registry_path)
        assert registry.issuers["cez-as"].rules == []

    def test_issuer_entry_default_rules_is_empty_list(self) -> None:
        entry = IssuerEntry(slug="x", display_name="X")
        assert entry.rules == []


class TestIssuerEntryWithRules:
    """``with_rules.yml`` round-trips through ``load_registry`` with rules
    parsed into ``Rule`` instances.
    """

    def test_cez_issuer_has_two_rules(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rules = registry.issuers["cez-as"].rules
        assert len(rules) == 2

    def test_first_rule_is_full_template(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rule = registry.issuers["cez-as"].rules[0]
        assert isinstance(rule, Rule)
        assert rule.id == "cez-invoice-2024-template"
        assert rule.partial is False
        assert rule.priority == 100
        assert rule.version == 1

    def test_second_rule_is_fingerprint_partial(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rule = registry.issuers["cez-as"].rules[1]
        assert isinstance(rule, Rule)
        assert rule.id == "cez-fingerprint"
        assert rule.partial is True

    def test_issuer_without_rules_block_has_empty_list(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        assert registry.issuers["plzensky-prazdroj"].rules == []


class TestRuleRoundTrip:
    """Match clauses and extract dicts survive parsing intact."""

    def test_full_rule_match_ocr_contains_preserved(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rule = registry.issuers["cez-as"].rules[0]
        assert rule.match.ocr_contains == ["IC: 45274649", "Faktura"]

    def test_full_rule_match_ocr_matches_preserved(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rule = registry.issuers["cez-as"].rules[0]
        assert rule.match.ocr_matches is not None
        assert len(rule.match.ocr_matches) == 1
        assert "Faktura" in rule.match.ocr_matches[0]

    def test_full_rule_extract_keys(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rule = registry.issuers["cez-as"].rules[0]
        assert set(rule.extract.keys()) == {
            "doc_type",
            "doc_number",
            "doc_currency",
            "doc_language",
        }

    def test_fingerprint_extract_allows_issuer_slug(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rule = registry.issuers["cez-as"].rules[1]
        assert "issuer_slug" in rule.extract
        assert rule.extract["issuer_slug"] == "cez-as"

    def test_fingerprint_extract_allows_issuer_display(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rule = registry.issuers["cez-as"].rules[1]
        assert rule.extract["issuer_display"] == "CEZ a.s."

    def test_fingerprint_match_ocr_contains_preserved(self, with_rules_path: Path) -> None:
        registry = load_registry(with_rules_path)
        rule = registry.issuers["cez-as"].rules[1]
        assert rule.match.ocr_contains == ["IC: 45274649"]


class TestCrossIssuerRuleIdUniqueness:
    """Rule ids must be unique across the entire registry, not just per
    issuer. The duplicate fixture has ``cez-fingerprint`` on both ``cez-as``
    and ``plzensky-prazdroj``.
    """

    def test_duplicate_rule_id_across_issuers_rejected(self, with_rules_duplicate_path: Path) -> None:
        with pytest.raises((RuntimeError, ValueError, ValidationError)):
            load_registry(with_rules_duplicate_path)

    def test_duplicate_error_mentions_first_issuer_slug(self, with_rules_duplicate_path: Path) -> None:
        with pytest.raises((RuntimeError, ValueError, ValidationError)) as exc_info:
            load_registry(with_rules_duplicate_path)
        assert "cez-as" in str(exc_info.value)

    def test_duplicate_error_mentions_second_issuer_slug(self, with_rules_duplicate_path: Path) -> None:
        with pytest.raises((RuntimeError, ValueError, ValidationError)) as exc_info:
            load_registry(with_rules_duplicate_path)
        assert "plzensky-prazdroj" in str(exc_info.value)

    def test_duplicate_error_mentions_rule_id(self, with_rules_duplicate_path: Path) -> None:
        with pytest.raises((RuntimeError, ValueError, ValidationError)) as exc_info:
            load_registry(with_rules_duplicate_path)
        assert "cez-fingerprint" in str(exc_info.value)


class TestCiphertextRegression:
    """Adding the rules field must not break the existing PGP-encrypted
    file detection.
    """

    def test_ciphertext_file_still_raises_runtime_error(self, tmp_path: Path) -> None:
        encrypted = tmp_path / "issuers.yml"
        shutil.copy(FIXTURES / "ciphertext.yml", encrypted)
        with pytest.raises(RuntimeError, match="git filter"):
            load_registry(encrypted)


class TestSerializeOmitsEmptyRules:
    """The new ``rules: list[Rule]`` field on ``IssuerEntry`` defaults to ``[]``.
    The serializer must not emit a ``rules: []`` line for issuers that had no
    ``rules:`` block in the source — the wire format for legacy entries must
    stay unchanged.
    """

    def test_legacy_issuer_round_trip_has_no_rules_key(self, valid_registry_path: Path) -> None:
        from bim.commands.doc.shared.issuers import _serialize

        registry = load_registry(valid_registry_path)
        serialized = _serialize(registry)
        # Neither legacy issuer in valid.yml had a rules: block; the
        # serializer must not introduce one.
        assert "rules:" not in serialized

    def test_with_aliases_round_trip_has_no_rules_key(self, aliases_registry_path: Path) -> None:
        from bim.commands.doc.shared.issuers import _serialize

        registry = load_registry(aliases_registry_path)
        serialized = _serialize(registry)
        assert "rules:" not in serialized

    def test_legacy_issuer_round_trip_preserves_other_fields(self, valid_registry_path: Path) -> None:
        from bim.commands.doc.shared.issuers import _serialize

        registry = load_registry(valid_registry_path)
        serialized = _serialize(registry)
        # Sanity: the fields that WERE in the source still come through.
        assert "cez-as:" in serialized
        assert "display_name: CEZ a.s." in serialized
        assert "plzensky-prazdroj:" in serialized

    def test_mixed_registry_only_emits_rules_for_issuers_that_have_them(self, with_rules_path: Path) -> None:
        from bim.commands.doc.shared.issuers import _serialize

        # with_rules.yml: cez-as HAS rules, plzensky-prazdroj does NOT.
        registry = load_registry(with_rules_path)
        serialized = _serialize(registry)
        # cez-as's rules must round-trip.
        assert "rules:" in serialized
        # ...but it must appear exactly once (under cez-as), not twice.
        assert serialized.count("rules:") == 1
