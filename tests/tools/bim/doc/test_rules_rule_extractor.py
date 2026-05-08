"""Tests for the per-rule field extractor in ``bim.commands.doc.shared.rules.extractor``.

These tests are the spec for the to-be-implemented extractor. They will fail
with ``ImportError`` until the implementation lands; that is expected.

Note: this file is named ``test_rules_rule_extractor.py`` to disambiguate from
the unrelated LLM-extractor tests in ``test_extractor.py``.

Assumptions made where the spec was ambiguous:

- ``apply_extract`` returns ``None`` whenever any single ``ExtractSpec`` in the
  rule fails to produce a value (no match, missing source field, transform
  raises). The whole rule is treated as all-or-nothing — partial pinned dicts
  are never returned.
- Literal values (``str``, ``int``, ``float``) bypass the extraction pipeline
  entirely and are copied into the output verbatim. They cannot fail.
- For ``from: ocr_match`` the matcher's pre-computed ``captures`` dict is
  consulted only for the matcher-side regexes; per-spec ``pattern`` is
  re-applied with ``re.search`` against ``ocr_text`` to extract the spec's
  capture group. This matches the spec wording: "the spec's ``pattern`` is
  applied to ``ocr_text``".
- ``from: filename_match`` uses ``source.original_filename``; the spec's
  ``pattern`` is applied to that filename. ``groups: [year, month]`` plus
  ``format: "year-month"`` is the only multi-group composition allowed in v1
  — any other ``format`` with multiple groups returns ``None``.
- ``from: email_date`` returns ``source.email_date`` verbatim as a string. No
  transform is applied; downstream code is responsible for parsing if needed.
- The transform registry is the canonical seven names. Any transform
  exception (e.g. ``ValueError`` from ``int("abc")``) is caught and turned
  into ``None`` for the whole rule — extractor failures must not raise.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

# Module under test (will fail to import until the extractor lands).
from bim.commands.doc.shared.rules.extractor import apply_extract
from bim.commands.doc.shared.rules.matcher import evaluate_match
from bim.commands.doc.shared.rules.models import (
    ExtractSpec,
    MatchClauses,
    Rule,
    SourceMetadata,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule(
    extract: dict[str, Any],
    *,
    match: dict[str, Any] | None = None,
    rule_id: str = "test-rule",
) -> Rule:
    """Build a minimal valid ``Rule`` with the given extract block."""
    if match is None:
        # Default: a benign clause so Rule-level validation passes.
        match = {"ocr_contains": ["faktura"]}
    return Rule(
        id=rule_id,
        match=MatchClauses(**match),
        extract=extract,
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


def _captures_for(rule: Rule, ocr_text: str, source: SourceMetadata) -> dict[str, list[re.Match[str]]]:
    """Run the matcher and return its captures so apply_extract gets real input."""
    return evaluate_match(rule, ocr_text, source).captures


# ---------------------------------------------------------------------------
# Literal values
# ---------------------------------------------------------------------------


class TestLiteralValues:
    def test_two_literal_strings(self) -> None:
        rule = _rule({"doc_currency": "CZK", "doc_language": "cs"})
        result = apply_extract(rule, "Faktura", _source(), {})
        assert result == {"doc_currency": "CZK", "doc_language": "cs"}

    def test_literal_int_allowed(self) -> None:
        rule = _rule({"doc_amount": 1000, "doc_currency": "CZK"})
        result = apply_extract(rule, "Faktura", _source(), {})
        assert result == {"doc_amount": 1000, "doc_currency": "CZK"}
        assert isinstance(result["doc_amount"], int)

    def test_literal_float_allowed(self) -> None:
        rule = _rule({"doc_amount": 1234.5, "doc_currency": "CZK"})
        result = apply_extract(rule, "Faktura", _source(), {})
        assert result == {"doc_amount": 1234.5, "doc_currency": "CZK"}
        assert isinstance(result["doc_amount"], float)

    def test_literal_only_ignores_ocr_text(self) -> None:
        rule = _rule({"doc_currency": "CZK"})
        # Empty OCR text and empty captures must still succeed.
        result = apply_extract(rule, "", _source(), {})
        assert result == {"doc_currency": "CZK"}


# ---------------------------------------------------------------------------
# from: ocr_match
# ---------------------------------------------------------------------------


class TestFromOcrMatch:
    def test_single_group_extracts_string(self) -> None:
        rule = _rule(
            {
                "doc_number": ExtractSpec(**{"from": "ocr_match", "pattern": r"Faktura č\.\s*(\d{10})", "group": 1}),
            },
            match={"ocr_matches": [r"Faktura č\.\s*(\d{10})"]},
        )
        ocr = "Faktura č. 7102105594"
        captures = _captures_for(rule, ocr, _source())
        result = apply_extract(rule, ocr, _source(), captures)
        assert result == {"doc_number": "7102105594"}

    def test_strip_whitespace_to_int_transform(self) -> None:
        rule = _rule(
            {
                "doc_amount": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Celkem k úhradě:\s*([\d\s]+) CZK",
                        "group": 1,
                        "transform": "strip_whitespace_to_int",
                    }
                ),
            },
            match={"ocr_matches": [r"Celkem k úhradě:\s*([\d\s]+) CZK"]},
        )
        ocr = "Celkem k úhradě: 4 218 CZK"
        captures = _captures_for(rule, ocr, _source())
        result = apply_extract(rule, ocr, _source(), captures)
        assert result == {"doc_amount": 4218}
        assert isinstance(result["doc_amount"], int)

    def test_parse_date_transform_with_format(self) -> None:
        rule = _rule(
            {
                "doc_date": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Datum vystavení:\s*(\d{2}\.\d{2}\.\d{4})",
                        "group": 1,
                        "transform": "parse_date",
                        "format": "%d.%m.%Y",
                    }
                ),
            },
            match={"ocr_matches": [r"Datum vystavení:\s*(\d{2}\.\d{2}\.\d{4})"]},
        )
        ocr = "Datum vystavení: 15.11.2024"
        captures = _captures_for(rule, ocr, _source())
        result = apply_extract(rule, ocr, _source(), captures)
        assert result == {"doc_date": date(2024, 11, 15)}
        assert isinstance(result["doc_date"], date)

    def test_pattern_no_match_returns_none_for_whole_rule(self) -> None:
        # Rule has a pattern that won't appear in OCR; the whole rule fails.
        rule = _rule(
            {
                "doc_number": ExtractSpec(**{"from": "ocr_match", "pattern": r"Smlouva č\.\s*(\d{10})", "group": 1}),
            },
        )
        result = apply_extract(rule, "Faktura č. 7102105594", _source(), {})
        assert result is None

    def test_one_failing_spec_voids_whole_rule(self) -> None:
        # Two specs; first succeeds, second's pattern doesn't match.
        rule = _rule(
            {
                "doc_number": ExtractSpec(**{"from": "ocr_match", "pattern": r"Faktura č\.\s*(\d{10})", "group": 1}),
                "doc_amount": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Smlouva\s*č\.\s*(\d+)",
                        "group": 1,
                    }
                ),
            },
        )
        result = apply_extract(rule, "Faktura č. 7102105594", _source(), {})
        assert result is None


# ---------------------------------------------------------------------------
# from: filename_match
# ---------------------------------------------------------------------------


class TestFromFilenameMatch:
    def test_year_month_combines_two_groups_into_date(self) -> None:
        rule = _rule(
            {
                "doc_date": ExtractSpec(
                    **{
                        "from": "filename_match",
                        "pattern": r"vypis_(\d{4})_(\d{2})\.pdf",
                        "groups": [1, 2],
                        "format": "year-month",
                    }
                ),
            },
            match={"original_filename_matches": r"vypis_(\d{4})_(\d{2})\.pdf"},
        )
        source = _source(original_filename="vypis_2024_11.pdf")
        captures = _captures_for(rule, "", source)
        result = apply_extract(rule, "", source, captures)
        assert result == {"doc_date": date(2024, 11, 1)}
        assert isinstance(result["doc_date"], date)

    def test_no_filename_returns_none(self) -> None:
        rule = _rule(
            {
                "doc_date": ExtractSpec(
                    **{
                        "from": "filename_match",
                        "pattern": r"vypis_(\d{4})_(\d{2})\.pdf",
                        "groups": [1, 2],
                        "format": "year-month",
                    }
                ),
            },
        )
        # source.original_filename is None.
        result = apply_extract(rule, "", _source(), {})
        assert result is None

    def test_pattern_does_not_match_filename_returns_none(self) -> None:
        rule = _rule(
            {
                "doc_date": ExtractSpec(
                    **{
                        "from": "filename_match",
                        "pattern": r"vypis_(\d{4})_(\d{2})\.pdf",
                        "groups": [1, 2],
                        "format": "year-month",
                    }
                ),
            },
        )
        source = _source(original_filename="something_else.pdf")
        result = apply_extract(rule, "", source, {})
        assert result is None

    def test_multi_group_with_unsupported_format_returns_none(self) -> None:
        # groups: [1, 2] with anything other than "year-month" is unsupported in v1.
        rule = _rule(
            {
                "doc_date": ExtractSpec(
                    **{
                        "from": "filename_match",
                        "pattern": r"vypis_(\d{4})_(\d{2})\.pdf",
                        "groups": [1, 2],
                        "format": "%d.%m.%Y",
                    }
                ),
            },
        )
        source = _source(original_filename="vypis_2024_11.pdf")
        result = apply_extract(rule, "", source, {})
        assert result is None


# ---------------------------------------------------------------------------
# from: email_date
# ---------------------------------------------------------------------------


class TestFromEmailDate:
    def test_email_date_returned_verbatim_as_string(self) -> None:
        rule = _rule(
            {"doc_date": ExtractSpec(**{"from": "email_date"})},
            match={"email_from_domain": ["cez.cz"]},
        )
        source = _source(
            source_kind="email",
            email_from="noreply@cez.cz",
            email_date="2024-11-15",
        )
        result = apply_extract(rule, "", source, {})
        assert result == {"doc_date": "2024-11-15"}
        assert isinstance(result["doc_date"], str)

    def test_no_email_date_returns_none(self) -> None:
        rule = _rule(
            {"doc_date": ExtractSpec(**{"from": "email_date"})},
            match={"email_from_domain": ["cez.cz"]},
        )
        # source.email_date is None.
        source = _source(source_kind="email", email_from="noreply@cez.cz")
        result = apply_extract(rule, "", source, {})
        assert result is None

    def test_email_date_with_parse_date_transform_is_applied(self) -> None:
        # The transform: clause on an email_date source must be honoured;
        # earlier versions short-circuited and returned the raw string.
        from datetime import date

        rule = _rule(
            {
                "doc_date": ExtractSpec(
                    **{
                        "from": "email_date",
                        "transform": "parse_date",
                        "format": "%Y-%m-%d",
                    }
                )
            },
            match={"email_from_domain": ["cez.cz"]},
        )
        source = _source(
            source_kind="email",
            email_from="noreply@cez.cz",
            email_date="2024-11-15",
        )
        result = apply_extract(rule, "", source, {})
        assert result == {"doc_date": date(2024, 11, 15)}


# ---------------------------------------------------------------------------
# Transforms (all 7) reachable through ExtractSpec
# ---------------------------------------------------------------------------


class TestTransformsViaExtractSpec:
    """Each transform must be invokable through an ExtractSpec on a happy path."""

    def test_lowercase(self) -> None:
        rule = _rule(
            {
                "issuer_slug": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Issuer:\s*(\w+)",
                        "group": 1,
                        "transform": "lowercase",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Issuer: CEZPRODEJ", _source(), {})
        assert result == {"issuer_slug": "cezprodej"}

    def test_uppercase(self) -> None:
        rule = _rule(
            {
                "doc_currency": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Currency:\s*(\w+)",
                        "group": 1,
                        "transform": "uppercase",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Currency: czk", _source(), {})
        assert result == {"doc_currency": "CZK"}

    def test_strip(self) -> None:
        rule = _rule(
            {
                "doc_number": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Number:(.+)$",
                        "group": 1,
                        "transform": "strip",
                    }
                ),
            },
        )
        # The capture group itself can hold padded content if pattern allows.
        result = apply_extract(rule, "Number:   ABC123  ", _source(), {})
        assert result is not None
        assert result["doc_number"] == "ABC123"

    def test_slugify(self) -> None:
        from bim.commands.doc.shared import naming

        rule = _rule(
            {
                "issuer_slug": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Issuer:\s*(.+?)\s*$",
                        "group": 1,
                        "transform": "slugify",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Issuer: ČEZ Prodej", _source(), {})
        assert result is not None
        assert result["issuer_slug"] == naming.slugify("ČEZ Prodej")

    def test_strip_whitespace_to_int(self) -> None:
        rule = _rule(
            {
                "doc_amount": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Amount:\s*([\d\s]+)",
                        "group": 1,
                        "transform": "strip_whitespace_to_int",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Amount: 4 218", _source(), {})
        assert result == {"doc_amount": 4218}

    def test_strip_whitespace_to_decimal(self) -> None:
        rule = _rule(
            {
                "doc_amount": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Amount:\s*([\d\s,\.]+)",
                        "group": 1,
                        "transform": "strip_whitespace_to_decimal",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Amount: 1 234,56", _source(), {})
        assert result is not None
        assert result["doc_amount"] == Decimal("1234.56")

    def test_parse_date(self) -> None:
        rule = _rule(
            {
                "doc_date": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Date:\s*(\d{2}\.\d{2}\.\d{4})",
                        "group": 1,
                        "transform": "parse_date",
                        "format": "%d.%m.%Y",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Date: 15.11.2024", _source(), {})
        assert result == {"doc_date": date(2024, 11, 15)}


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


class TestTransformFailureReturnsNone:
    def test_int_transform_on_non_numeric_returns_none(self) -> None:
        # Pattern matches "abc" — the transform will raise ValueError; the
        # extractor must catch it and return None for the whole rule.
        rule = _rule(
            {
                "doc_amount": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Amount:\s*(\w+)",
                        "group": 1,
                        "transform": "strip_whitespace_to_int",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Amount: abc", _source(), {})
        assert result is None

    def test_decimal_transform_on_non_numeric_returns_none(self) -> None:
        rule = _rule(
            {
                "doc_amount": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Amount:\s*(\w+)",
                        "group": 1,
                        "transform": "strip_whitespace_to_decimal",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Amount: bogus", _source(), {})
        assert result is None

    def test_parse_date_on_invalid_date_returns_none(self) -> None:
        rule = _rule(
            {
                "doc_date": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Date:\s*(\S+)",
                        "group": 1,
                        "transform": "parse_date",
                        "format": "%d.%m.%Y",
                    }
                ),
            },
        )
        result = apply_extract(rule, "Date: not-a-date", _source(), {})
        assert result is None


# ---------------------------------------------------------------------------
# Mixed extract block: the spec's full CEZ rule
# ---------------------------------------------------------------------------


class TestFullCezRule:
    """The full CEZ rule has 4 OCR pattern fields + 2 literals — all must succeed."""

    def _build_rule(self) -> Rule:
        return _rule(
            {
                # Literals
                "doc_currency": "CZK",
                "doc_language": "cs",
                # OCR-extracted strings
                "issuer_slug": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"(ČEZ Prodej)",
                        "group": 1,
                        "transform": "slugify",
                    }
                ),
                "doc_number": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Faktura č\.\s*(\d{10})",
                        "group": 1,
                    }
                ),
                # OCR-extracted amount with int transform
                "doc_amount": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Celkem k úhradě:\s*([\d\s]+) CZK",
                        "group": 1,
                        "transform": "strip_whitespace_to_int",
                    }
                ),
                # OCR-extracted date with parse_date transform
                "doc_date": ExtractSpec(
                    **{
                        "from": "ocr_match",
                        "pattern": r"Datum vystavení:\s*(\d{2}\.\d{2}\.\d{4})",
                        "group": 1,
                        "transform": "parse_date",
                        "format": "%d.%m.%Y",
                    }
                ),
            },
            match={
                "ocr_contains": ["Faktura", "ČEZ Prodej"],
                "ocr_matches": [r"Faktura č\.\s*(\d{10})"],
            },
            rule_id="cez-invoice-2024-template",
        )

    def test_all_six_fields_extracted_with_correct_types(self) -> None:
        from bim.commands.doc.shared import naming

        rule = self._build_rule()
        ocr = "ČEZ Prodej a.s. Faktura č. 7102105594 Datum vystavení: 15.11.2024 Celkem k úhradě: 4 218 CZK"
        source = _source()
        captures = _captures_for(rule, ocr, source)
        result = apply_extract(rule, ocr, source, captures)

        assert result is not None
        assert set(result.keys()) == {
            "doc_currency",
            "doc_language",
            "issuer_slug",
            "doc_number",
            "doc_amount",
            "doc_date",
        }
        # Literals
        assert result["doc_currency"] == "CZK"
        assert result["doc_language"] == "cs"
        # OCR extractions
        assert result["issuer_slug"] == naming.slugify("ČEZ Prodej")
        assert result["doc_number"] == "7102105594"
        assert result["doc_amount"] == 4218
        assert result["doc_date"] == date(2024, 11, 15)

    def test_doc_amount_is_int_not_str(self) -> None:
        rule = self._build_rule()
        ocr = "ČEZ Prodej a.s. Faktura č. 7102105594 Datum vystavení: 15.11.2024 Celkem k úhradě: 4 218 CZK"
        source = _source()
        captures = _captures_for(rule, ocr, source)
        result = apply_extract(rule, ocr, source, captures)
        assert result is not None
        assert isinstance(result["doc_amount"], int)
        assert not isinstance(result["doc_amount"], bool)

    def test_doc_date_is_date_not_str(self) -> None:
        rule = self._build_rule()
        ocr = "ČEZ Prodej a.s. Faktura č. 7102105594 Datum vystavení: 15.11.2024 Celkem k úhradě: 4 218 CZK"
        source = _source()
        captures = _captures_for(rule, ocr, source)
        result = apply_extract(rule, ocr, source, captures)
        assert result is not None
        assert isinstance(result["doc_date"], date)

    def test_string_fields_are_str(self) -> None:
        rule = self._build_rule()
        ocr = "ČEZ Prodej a.s. Faktura č. 7102105594 Datum vystavení: 15.11.2024 Celkem k úhradě: 4 218 CZK"
        source = _source()
        captures = _captures_for(rule, ocr, source)
        result = apply_extract(rule, ocr, source, captures)
        assert result is not None
        for key in ("doc_currency", "doc_language", "issuer_slug", "doc_number"):
            assert isinstance(result[key], str), f"{key} should be str, got {type(result[key]).__name__}"
