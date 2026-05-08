"""Tests for the rule matcher in ``bim.commands.doc.shared.rules.matcher``.

These tests are the spec for the to-be-implemented matcher. They will fail
with ``ImportError`` until the implementation lands; that is expected.

Assumptions made where the spec was ambiguous:

- ``MatchResult`` is a stdlib ``@dataclass(frozen=True)``. Mutating any of
  its fields raises ``dataclasses.FrozenInstanceError``.
- ``MatchResult.captures`` is keyed by clause name and only contains entries
  for clauses that actually contributed ``re.Match`` objects (i.e.
  ``ocr_matches``, ``email_subject_matches``, ``original_filename_matches``).
  String-only clauses (``ocr_contains``, ``email_from_domain``,
  ``email_subject_contains``) do not populate ``captures``.
- An empty ``MatchClauses()`` (no clauses set) yields ``matched=False``
  rather than raising. This is defensive: ``Rule`` rejects such clauses at
  construction time, so this branch only triggers if a caller hand-builds a
  ``MatchClauses`` directly.
- ``ocr_contains`` matches use case-fold + ASCII-fold on both sides, so
  ``"IC"`` matches ``"IČ"`` and vice versa, and ``"FAKTURA"`` matches
  ``"faktura"``.
- ``ocr_matches`` regexes run against the raw ``ocr_text`` (case-sensitive
  by default). Authors opt into case-insensitivity with inline ``(?i)``.
- Source-irrelevant clauses (e.g. ``email_from_domain`` with no
  ``email_from``) yield ``matched=False`` silently. They never raise.
- A multi-clause rule is AND: every set clause must match for
  ``MatchResult.matched`` to be ``True``.
- ``email_from_domain`` is a suffix match against the address's domain
  portion, case-insensitive. ``"noreply@CEZ.CZ"`` with clause ``["cez.cz"]``
  matches.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

import pytest

# Module under test (will fail to import until the matcher lands).
from bim.commands.doc.shared.rules.matcher import MatchResult, evaluate_match
from bim.commands.doc.shared.rules.models import MatchClauses, Rule, SourceMetadata

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DUMMY_EXTRACT: dict[str, Any] = {"doc_type": "invoice"}


def _rule(match: dict[str, Any], *, rule_id: str = "test-rule") -> Rule:
    """Build a minimal valid ``Rule`` with the given match clauses."""
    return Rule(
        id=rule_id,
        match=MatchClauses(**match),
        extract=dict(_DUMMY_EXTRACT),
    )


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


# ---------------------------------------------------------------------------
# ocr_contains
# ---------------------------------------------------------------------------


class TestOcrContains:
    def test_all_substrings_present_matches(self) -> None:
        rule = _rule({"ocr_contains": ["Faktura", "IČ"]})
        result = evaluate_match(rule, "Faktura č. 7102105594 IČ: 45274649", _source())
        assert result.matched is True

    def test_one_substring_missing_does_not_match(self) -> None:
        rule = _rule({"ocr_contains": ["Faktura", "Smlouva"]})
        result = evaluate_match(rule, "Faktura č. 7102105594", _source())
        assert result.matched is False

    def test_single_string_coerced_to_list_of_one(self) -> None:
        # MatchClauses coerces "foo" -> ["foo"]; matcher must handle list-of-one.
        rule = _rule({"ocr_contains": "Faktura"})
        result = evaluate_match(rule, "Faktura č. 7102105594", _source())
        assert result.matched is True

    def test_case_fold_matches_uppercase_clause_against_lowercase_text(self) -> None:
        rule = _rule({"ocr_contains": ["FAKTURA"]})
        result = evaluate_match(rule, "faktura č. 7102105594", _source())
        assert result.matched is True

    def test_ascii_fold_matches_plain_clause_against_diacritic_text(self) -> None:
        rule = _rule({"ocr_contains": ["IC: 45274649"]})
        result = evaluate_match(rule, "IČ: 45274649", _source())
        assert result.matched is True

    def test_ascii_fold_matches_diacritic_clause_against_plain_text(self) -> None:
        rule = _rule({"ocr_contains": ["IČ: 45274649"]})
        result = evaluate_match(rule, "IC: 45274649", _source())
        assert result.matched is True

    def test_empty_ocr_text_does_not_match(self) -> None:
        rule = _rule({"ocr_contains": ["Faktura"]})
        result = evaluate_match(rule, "", _source())
        assert result.matched is False

    def test_string_only_clause_does_not_populate_captures(self) -> None:
        rule = _rule({"ocr_contains": ["Faktura"]})
        result = evaluate_match(rule, "Faktura č. 7102105594", _source())
        assert "ocr_contains" not in result.captures


# ---------------------------------------------------------------------------
# ocr_matches
# ---------------------------------------------------------------------------


class TestOcrMatches:
    def test_single_matching_regex_records_capture(self) -> None:
        rule = _rule({"ocr_matches": [r"Faktura č\.\s*(\d{10})"]})
        result = evaluate_match(rule, "Faktura č. 7102105594", _source())
        assert result.matched is True
        assert "ocr_matches" in result.captures
        assert len(result.captures["ocr_matches"]) >= 1

    def test_two_matching_regexes_record_both_captures(self) -> None:
        rule = _rule(
            {
                "ocr_matches": [
                    r"Faktura č\.\s*(\d{10})",
                    r"IČ:\s*(\d+)",
                ],
            }
        )
        result = evaluate_match(rule, "Faktura č. 7102105594 IČ: 45274649", _source())
        assert result.matched is True
        assert len(result.captures["ocr_matches"]) == 2

    def test_one_regex_failing_does_not_match(self) -> None:
        rule = _rule(
            {
                "ocr_matches": [
                    r"Faktura č\.\s*(\d{10})",
                    r"Smlouva\s*č\.\s*(\d+)",
                ],
            }
        )
        result = evaluate_match(rule, "Faktura č. 7102105594", _source())
        assert result.matched is False

    def test_capture_groups_are_preserved(self) -> None:
        rule = _rule({"ocr_matches": [r"Faktura č\.\s*(\d{10})"]})
        result = evaluate_match(rule, "Faktura č. 7102105594", _source())
        assert result.matched is True
        captured = result.captures["ocr_matches"][0]
        assert isinstance(captured, re.Match)
        assert captured.group(1) == "7102105594"

    def test_inline_case_insensitive_flag_matches_uppercase(self) -> None:
        rule = _rule({"ocr_matches": [r"(?i)faktura"]})
        result = evaluate_match(rule, "FAKTURA č. 7102105594", _source())
        assert result.matched is True


# ---------------------------------------------------------------------------
# email_from_domain
# ---------------------------------------------------------------------------


class TestEmailFromDomain:
    def test_lowercase_sender_matches_lowercase_clause(self) -> None:
        rule = _rule({"email_from_domain": ["cez.cz"]})
        source = _source(source_kind="email", email_from="noreply@cez.cz")
        result = evaluate_match(rule, "", source)
        assert result.matched is True

    def test_uppercase_sender_matches_lowercase_clause(self) -> None:
        rule = _rule({"email_from_domain": ["cez.cz"]})
        source = _source(source_kind="email", email_from="noreply@CEZ.CZ")
        result = evaluate_match(rule, "", source)
        assert result.matched is True

    def test_unrelated_sender_does_not_match(self) -> None:
        rule = _rule({"email_from_domain": ["cez.cz"]})
        source = _source(source_kind="email", email_from="noreply@example.com")
        result = evaluate_match(rule, "", source)
        assert result.matched is False

    def test_missing_email_from_does_not_match_and_does_not_raise(self) -> None:
        rule = _rule({"email_from_domain": ["cez.cz"]})
        source = _source()  # email_from is None
        result = evaluate_match(rule, "", source)
        assert result.matched is False

    def test_string_only_clause_does_not_populate_captures(self) -> None:
        rule = _rule({"email_from_domain": ["cez.cz"]})
        source = _source(source_kind="email", email_from="noreply@cez.cz")
        result = evaluate_match(rule, "", source)
        assert "email_from_domain" not in result.captures


# ---------------------------------------------------------------------------
# email_subject_contains
# ---------------------------------------------------------------------------


class TestEmailSubjectContains:
    def test_substring_present_case_insensitive(self) -> None:
        rule = _rule({"email_subject_contains": ["faktura"]})
        source = _source(source_kind="email", email_subject="Faktura cez 11/2024")
        result = evaluate_match(rule, "", source)
        assert result.matched is True

    def test_substring_absent_does_not_match(self) -> None:
        rule = _rule({"email_subject_contains": ["smlouva"]})
        source = _source(source_kind="email", email_subject="Faktura cez 11/2024")
        result = evaluate_match(rule, "", source)
        assert result.matched is False

    def test_missing_subject_does_not_match_and_does_not_raise(self) -> None:
        rule = _rule({"email_subject_contains": ["faktura"]})
        source = _source()  # email_subject is None
        result = evaluate_match(rule, "", source)
        assert result.matched is False


# ---------------------------------------------------------------------------
# email_subject_matches
# ---------------------------------------------------------------------------


class TestEmailSubjectMatches:
    def test_regex_match_records_capture(self) -> None:
        rule = _rule({"email_subject_matches": [r"Faktura č\.\s*(\d{10})"]})
        source = _source(source_kind="email", email_subject="Faktura č. 7102105594")
        result = evaluate_match(rule, "", source)
        assert result.matched is True
        assert "email_subject_matches" in result.captures
        captured = result.captures["email_subject_matches"][0]
        assert isinstance(captured, re.Match)
        assert captured.group(1) == "7102105594"

    def test_regex_no_match_does_not_match(self) -> None:
        rule = _rule({"email_subject_matches": [r"Smlouva\s*č\.\s*(\d+)"]})
        source = _source(source_kind="email", email_subject="Faktura č. 7102105594")
        result = evaluate_match(rule, "", source)
        assert result.matched is False

    def test_missing_subject_does_not_match_and_does_not_raise(self) -> None:
        rule = _rule({"email_subject_matches": [r"Faktura č\.\s*(\d{10})"]})
        source = _source()  # email_subject is None
        result = evaluate_match(rule, "", source)
        assert result.matched is False


# ---------------------------------------------------------------------------
# original_filename_matches
# ---------------------------------------------------------------------------


class TestOriginalFilenameMatches:
    def test_regex_match_records_single_capture(self) -> None:
        rule = _rule({"original_filename_matches": r"vypis_(\d{4})_(\d{2})\.pdf"})
        source = _source(original_filename="vypis_2024_11.pdf")
        result = evaluate_match(rule, "", source)
        assert result.matched is True
        assert "original_filename_matches" in result.captures
        assert len(result.captures["original_filename_matches"]) == 1
        captured = result.captures["original_filename_matches"][0]
        assert isinstance(captured, re.Match)
        assert captured.group(1) == "2024"
        assert captured.group(2) == "11"

    def test_regex_no_match_does_not_match(self) -> None:
        rule = _rule({"original_filename_matches": r"vypis_(\d{4})_(\d{2})\.pdf"})
        source = _source(original_filename="invoice.pdf")
        result = evaluate_match(rule, "", source)
        assert result.matched is False

    def test_missing_filename_does_not_match_and_does_not_raise(self) -> None:
        rule = _rule({"original_filename_matches": r"vypis_(\d{4})_(\d{2})\.pdf"})
        source = _source()  # original_filename is None
        result = evaluate_match(rule, "", source)
        assert result.matched is False


# ---------------------------------------------------------------------------
# Combined behaviors (AND across clauses)
# ---------------------------------------------------------------------------


class TestCombinedClauses:
    def test_all_clauses_pass_yields_match(self) -> None:
        # Mirrors the spec's full CEZ rule: ocr_contains + ocr_matches.
        rule = _rule(
            {
                "ocr_contains": ["IČ: 45274649", "Faktura"],
                "ocr_matches": [r"Faktura č\.\s*(\d{10})"],
            },
            rule_id="cez-invoice-2024-template",
        )
        result = evaluate_match(
            rule,
            "Faktura č. 7102105594 IČ: 45274649 Datum vystavení: 15.11.2024",
            _source(),
        )
        assert result.matched is True
        assert "ocr_matches" in result.captures
        assert result.captures["ocr_matches"][0].group(1) == "7102105594"

    def test_one_clause_failing_blocks_match(self) -> None:
        rule = _rule(
            {
                "ocr_contains": ["IČ: 45274649", "Faktura"],
                "ocr_matches": [r"Faktura č\.\s*(\d{10})"],
            }
        )
        # ocr_contains passes, ocr_matches fails (no 10-digit number).
        result = evaluate_match(rule, "Faktura IČ: 45274649", _source())
        assert result.matched is False

    def test_partial_rule_clause_combo_matches(self) -> None:
        # Mirrors the spec's partial CEZ rule: just ocr_contains.
        rule = _rule(
            {"ocr_contains": ["IČ: 45274649"]},
            rule_id="cez-issuer-partial",
        )
        result = evaluate_match(rule, "IČ: 45274649", _source())
        assert result.matched is True

    def test_email_and_ocr_clauses_both_required(self) -> None:
        rule = _rule(
            {
                "ocr_contains": ["Faktura"],
                "email_from_domain": ["cez.cz"],
            }
        )
        # Both pass.
        result = evaluate_match(
            rule,
            "Faktura č. 7102105594",
            _source(source_kind="email", email_from="noreply@cez.cz"),
        )
        assert result.matched is True
        # OCR passes but sender doesn't.
        result = evaluate_match(
            rule,
            "Faktura č. 7102105594",
            _source(source_kind="email", email_from="noreply@example.com"),
        )
        assert result.matched is False

    def test_source_irrelevant_clause_yields_no_match_silently(self) -> None:
        # Filesystem source, no email metadata. Rule asks for email_from_domain.
        rule = _rule({"email_from_domain": ["cez.cz"]})
        result = evaluate_match(rule, "Faktura", _source(source_kind="filesystem"))
        assert result.matched is False


# ---------------------------------------------------------------------------
# MatchResult shape
# ---------------------------------------------------------------------------


class TestMatchResultShape:
    def test_match_result_is_frozen(self) -> None:
        rule = _rule({"ocr_contains": ["Faktura"]})
        result = evaluate_match(rule, "Faktura", _source())
        with pytest.raises(dataclasses.FrozenInstanceError):
            # setattr bypasses static type checking; the runtime check is the point.
            setattr(result, "matched", False)

    def test_match_result_captures_field_is_frozen(self) -> None:
        rule = _rule({"ocr_contains": ["Faktura"]})
        result = evaluate_match(rule, "Faktura", _source())
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, "captures", {})

    def test_failing_match_returns_match_result_not_none(self) -> None:
        rule = _rule({"ocr_contains": ["Smlouva"]})
        result = evaluate_match(rule, "Faktura", _source())
        assert isinstance(result, MatchResult)
        assert result.matched is False


# ---------------------------------------------------------------------------
# Defensive: empty MatchClauses (cannot occur via Rule, can via direct ctor)
# ---------------------------------------------------------------------------


class TestEmptyMatchClauses:
    def test_match_clauses_with_no_set_fields_yield_no_match(self) -> None:
        # Hand-build a rule-like object so we bypass Rule's
        # at-least-one-clause validator. The matcher must not raise on this.
        empty_clauses = MatchClauses()

        @dataclasses.dataclass(frozen=True)
        class _RuleStub:
            id: str
            match: MatchClauses

        stub = _RuleStub(id="stub", match=empty_clauses)
        result = evaluate_match(stub, "anything", _source())
        assert result.matched is False
