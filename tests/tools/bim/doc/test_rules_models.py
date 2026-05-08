"""Tests for the rule schema models in bim.commands.doc.shared.rules.models.

These tests are the spec for the to-be-implemented Pydantic models. They will
fail with ImportError until the implementation lands; that is expected.

Assumptions made where the spec was ambiguous:

- ``RuleResult`` and ``SourceMetadata`` are stdlib ``@dataclass(frozen=True)``
  (the spec says "frozen dataclass"), not Pydantic models.
- For ``ExtractSpec.from_ == "email_date"``, ``transform`` and ``format`` are
  still permitted (spec only forbids ``pattern``, ``group``, ``groups``).
- Reserved-key validation in ``Rule.extract`` runs before allowed-name
  validation, so when both apply the reserved-name error is raised.
- "Allowed extract field names ... is OK" is interpreted strictly: any
  non-allowed, non-reserved key in ``extract`` raises ``ValidationError``.
- A non-partial rule (``partial: false``, the default) with ``extract={}``
  is rejected: such a rule pins nothing, so it has no effect. A partial
  rule with ``extract={}`` is also rejected for the same reason (a partial
  rule that pins NOTHING is meaningless). The rule id appears in the error
  message so YAML authors can locate the offending rule.
- ``ExtractSpec.from_`` is a closed enum: only the literal strings
  ``"ocr_match"``, ``"filename_match"``, and ``"email_date"`` are accepted.
  Empty strings, unknown values, and case variants (e.g. ``"OCR_MATCH"``)
  are all rejected.
- Values inside ``Rule.extract`` are constrained to ``ExtractSpec | str |
  int | float`` (matching the spec's "literal scalar or ExtractSpec dict"
  shape). Lists, ``None``, and dicts that do not parse as a valid
  ``ExtractSpec`` are rejected. Python's ``bool`` is a subclass of ``int``;
  the spec lists ``int`` so bool values are accepted via that path.
- Regex group indices in ``ExtractSpec.groups`` must be non-negative ints
  (``0`` is the whole-match group and is valid in ``re``). Negative
  indices are rejected, and an empty ``groups: []`` is rejected because a
  ``groups`` declaration with zero indices is meaningless.
"""

from __future__ import annotations

import dataclasses

import pytest

# Module under test (will fail to import until the models are implemented).
from bim.commands.doc.shared.rules.models import (
    ExtractSpec,
    MatchClauses,
    Rule,
    RuleResult,
    SourceMetadata,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Spec example fixtures
# ---------------------------------------------------------------------------


CEZ_FULL: dict = {
    "id": "cez-invoice-2024-template",
    "version": 1,
    "priority": 100,
    "enabled": True,
    "partial": False,
    "match": {
        "ocr_contains": ["IČ: 45274649", "Faktura"],
        "ocr_matches": ["Faktura č\\.\\s*(\\d{10})"],
    },
    "extract": {
        "doc_type": "invoice",
        "doc_number": {
            "from": "ocr_match",
            "pattern": "Faktura č\\.\\s*(\\d{10})",
            "group": 1,
        },
        "doc_date": {
            "from": "ocr_match",
            "pattern": "Datum vystavení:\\s*(\\d{2}\\.\\d{2}\\.\\d{4})",
            "group": 1,
            "format": "%d.%m.%Y",
            "transform": "parse_date",
        },
        "doc_amount": {
            "from": "ocr_match",
            "pattern": "Celkem k úhradě:\\s*([\\d\\s]+),\\d{2}\\s*Kč",
            "group": 1,
            "transform": "strip_whitespace_to_int",
        },
        "doc_currency": "CZK",
        "doc_language": "cs",
    },
    "confidence": 1.0,
}


CEZ_PARTIAL: dict = {
    "id": "cez-fingerprint",
    "partial": True,
    "match": {"ocr_contains": ["IČ: 45274649"]},
    "extract": {
        "issuer_slug": "cez-as",
        "issuer_display": "ČEZ a.s.",
        "doc_language": "cs",
    },
    "confidence": 1.0,
}


# ---------------------------------------------------------------------------
# MatchClauses
# ---------------------------------------------------------------------------


class TestMatchClausesFields:
    def test_all_fields_default_to_none(self) -> None:
        m = MatchClauses()
        assert m.ocr_contains is None
        assert m.ocr_matches is None
        assert m.email_from_domain is None
        assert m.email_subject_contains is None
        assert m.email_subject_matches is None
        assert m.original_filename_matches is None

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MatchClauses.model_validate({"unknown_clause": ["foo"]})

    def test_is_frozen(self) -> None:
        m = MatchClauses(ocr_contains=["foo"])
        with pytest.raises(ValidationError):
            setattr(m, "ocr_contains", ["bar"])


class TestMatchClausesStringCoercion:
    def test_ocr_contains_coerces_string_to_list(self) -> None:
        m = MatchClauses.model_validate({"ocr_contains": "hello"})
        assert m.ocr_contains == ["hello"]

    def test_ocr_matches_coerces_string_to_list(self) -> None:
        m = MatchClauses.model_validate({"ocr_matches": "foo.*"})
        assert m.ocr_matches == ["foo.*"]

    def test_email_from_domain_coerces_string_to_list(self) -> None:
        m = MatchClauses.model_validate({"email_from_domain": "example.com"})
        assert m.email_from_domain == ["example.com"]

    def test_email_subject_contains_coerces_string_to_list(self) -> None:
        m = MatchClauses.model_validate({"email_subject_contains": "Invoice"})
        assert m.email_subject_contains == ["Invoice"]

    def test_email_subject_matches_coerces_string_to_list(self) -> None:
        m = MatchClauses.model_validate({"email_subject_matches": r"Invoice \d+"})
        assert m.email_subject_matches == [r"Invoice \d+"]

    def test_original_filename_matches_stays_string(self) -> None:
        m = MatchClauses.model_validate({"original_filename_matches": r"foo_\d+\.pdf"})
        assert m.original_filename_matches == r"foo_\d+\.pdf"

    def test_list_values_passed_through(self) -> None:
        m = MatchClauses.model_validate({"ocr_contains": ["a", "b"]})
        assert m.ocr_contains == ["a", "b"]


class TestMatchClausesRegexValidation:
    def test_invalid_ocr_match_regex_raises(self) -> None:
        with pytest.raises(ValidationError):
            MatchClauses.model_validate({"ocr_matches": ["[invalid("]})

    def test_invalid_email_subject_match_regex_raises(self) -> None:
        with pytest.raises(ValidationError):
            MatchClauses.model_validate({"email_subject_matches": ["(unclosed"]})

    def test_invalid_original_filename_match_regex_raises(self) -> None:
        with pytest.raises(ValidationError):
            MatchClauses.model_validate({"original_filename_matches": "[bad("})

    def test_valid_complex_regex_accepted(self) -> None:
        m = MatchClauses.model_validate({"ocr_matches": [r"Faktura č\.\s*(\d{10})"]})
        assert m.ocr_matches == [r"Faktura č\.\s*(\d{10})"]


# ---------------------------------------------------------------------------
# ExtractSpec
# ---------------------------------------------------------------------------


class TestExtractSpecFields:
    def test_all_fields_default_to_none(self) -> None:
        spec = ExtractSpec.model_validate({"from": "email_date"})
        assert spec.from_ == "email_date"
        assert spec.pattern is None
        assert spec.group is None
        assert spec.groups is None
        assert spec.transform is None
        assert spec.format is None

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "email_date", "bogus": 1})

    def test_is_frozen(self) -> None:
        spec = ExtractSpec.model_validate({"from": "email_date"})
        with pytest.raises(ValidationError):
            setattr(spec, "format", "%Y")

    def test_from_alias_accepted_in_yaml_style_input(self) -> None:
        spec = ExtractSpec.model_validate({"from": "ocr_match", "pattern": r"(\d+)", "group": 1})
        assert spec.from_ == "ocr_match"


class TestExtractSpecFromEnumClosure:
    def test_unknown_from_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "banana"})

    def test_empty_from_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": ""})

    def test_uppercase_from_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "OCR_MATCH"})

    def test_other_unknown_from_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "foo_bar", "pattern": r"(\d+)", "group": 1})

    def test_missing_from_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"pattern": r"(\d+)", "group": 1})


class TestExtractSpecPatternRequirement:
    def test_ocr_match_without_pattern_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "ocr_match"})

    def test_filename_match_without_pattern_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "filename_match"})

    def test_ocr_match_pattern_must_compile(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "ocr_match", "pattern": "[invalid("})

    def test_filename_match_pattern_must_compile(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "filename_match", "pattern": "(unclosed"})

    def test_ocr_match_with_valid_pattern_accepted(self) -> None:
        spec = ExtractSpec.model_validate({"from": "ocr_match", "pattern": r"(\d{10})", "group": 1})
        assert spec.pattern == r"(\d{10})"
        assert spec.group == 1


class TestExtractSpecEmailDateConstraints:
    def test_email_date_with_pattern_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "email_date", "pattern": r"\d+"})

    def test_email_date_with_group_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "email_date", "group": 1})

    def test_email_date_with_groups_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate({"from": "email_date", "groups": [1, 2]})

    def test_email_date_alone_accepted(self) -> None:
        spec = ExtractSpec.model_validate({"from": "email_date"})
        assert spec.from_ == "email_date"


class TestExtractSpecTransformAllowlist:
    @pytest.mark.parametrize(
        "transform",
        [
            "strip_whitespace_to_int",
            "strip_whitespace_to_decimal",
            "parse_date",
            "lowercase",
            "uppercase",
            "strip",
            "slugify",
        ],
    )
    def test_known_transform_accepted(self, transform: str) -> None:
        spec = ExtractSpec.model_validate(
            {
                "from": "ocr_match",
                "pattern": r"(\d+)",
                "group": 1,
                "transform": transform,
            }
        )
        assert spec.transform == transform

    def test_unknown_transform_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ExtractSpec.model_validate(
                {
                    "from": "ocr_match",
                    "pattern": r"(\d+)",
                    "group": 1,
                    "transform": "do_a_barrel_roll",
                }
            )
        assert "do_a_barrel_roll" in str(exc_info.value)


class TestExtractSpecGroupExclusivity:
    def test_group_and_groups_together_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate(
                {
                    "from": "ocr_match",
                    "pattern": r"(\d+)-(\d+)",
                    "group": 1,
                    "groups": [1, 2],
                }
            )

    def test_groups_alone_accepted(self) -> None:
        spec = ExtractSpec.model_validate(
            {
                "from": "ocr_match",
                "pattern": r"(\d+)-(\d+)",
                "groups": [1, 2],
            }
        )
        assert spec.groups == [1, 2]
        assert spec.group is None


class TestExtractSpecGroupsIntegerConstraints:
    def test_zero_group_index_accepted(self) -> None:
        # group 0 = whole match, valid in stdlib re
        spec = ExtractSpec.model_validate(
            {
                "from": "ocr_match",
                "pattern": r"\d+",
                "groups": [0],
            }
        )
        assert spec.groups == [0]

    def test_negative_group_index_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate(
                {
                    "from": "ocr_match",
                    "pattern": r"(\d+)",
                    "groups": [-1],
                }
            )

    def test_empty_groups_list_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractSpec.model_validate(
                {
                    "from": "ocr_match",
                    "pattern": r"(\d+)",
                    "groups": [],
                }
            )


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


def _minimal_rule_data(**overrides: object) -> dict:
    """Smallest valid Rule input. Caller can override any key."""
    base: dict = {
        "id": "rule-x",
        "match": {"ocr_contains": ["foo"]},
        "extract": {"doc_type": "invoice"},
    }
    base.update(overrides)
    return base


class TestRuleDefaults:
    def test_minimal_rule_has_documented_defaults(self) -> None:
        rule = Rule.model_validate(_minimal_rule_data())
        assert rule.version == 1
        assert rule.priority == 50
        assert rule.enabled is True
        assert rule.partial is False
        assert rule.confidence == 1.0
        assert rule.notes is None

    def test_is_frozen(self) -> None:
        rule = Rule.model_validate(_minimal_rule_data())
        with pytest.raises(ValidationError):
            setattr(rule, "priority", 99)


class TestRuleIdAndVersion:
    def test_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Rule.model_validate(
                {
                    "match": {"ocr_contains": ["foo"]},
                    "extract": {"doc_type": "invoice"},
                }
            )

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Rule.model_validate(_minimal_rule_data(id=""))

    def test_id_with_colon_rejected(self) -> None:
        # The extraction_method regex uses ":" as a delimiter
        # (rule:<id>:v<n>); ids must not introduce extra colons.
        with pytest.raises(ValidationError) as exc_info:
            Rule.model_validate(_minimal_rule_data(id="my:rule"))
        msg = str(exc_info.value)
        assert "my:rule" in msg
        assert ":" in msg

    def test_version_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Rule.model_validate(_minimal_rule_data(version=0))

    def test_negative_version_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Rule.model_validate(_minimal_rule_data(version=-1))


class TestRuleMatchRequirement:
    def test_empty_match_clauses_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Rule.model_validate(_minimal_rule_data(match={}))

    def test_at_least_one_clause_accepted(self) -> None:
        rule = Rule.model_validate(_minimal_rule_data(match={"email_from_domain": ["example.com"]}))
        assert rule.match.email_from_domain == ["example.com"]


class TestRuleExtractReservedKeys:
    @pytest.mark.parametrize(
        "reserved",
        [
            "extraction_method",
            "id",
            "ingest_date",
            "ingest_source",
            "file_path",
            "file_sha256",
        ],
    )
    def test_reserved_extract_key_rejected_with_field_and_rule_id(self, reserved: str) -> None:
        data = _minimal_rule_data(
            id="my-rule-42",
            extract={"doc_type": "invoice", reserved: "anything"},
        )
        with pytest.raises(ValidationError) as exc_info:
            Rule.model_validate(data)
        msg = str(exc_info.value)
        assert reserved in msg
        assert "my-rule-42" in msg


class TestRuleExtractAllowedKeys:
    @pytest.mark.parametrize(
        "allowed",
        [
            "issuer_slug",
            "issuer_display",
            "doc_type",
            "doc_number",
            "doc_date",
            "doc_amount",
            "doc_currency",
            "doc_language",
        ],
    )
    def test_allowed_extract_key_accepted(self, allowed: str) -> None:
        rule = Rule.model_validate(_minimal_rule_data(extract={allowed: "value"}))
        assert allowed in rule.extract

    def test_unknown_extract_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Rule.model_validate(_minimal_rule_data(extract={"banana_count": 5}))


class TestRuleExtractValueShapes:
    def test_string_literal_value_accepted(self) -> None:
        rule = Rule.model_validate(_minimal_rule_data(extract={"doc_currency": "CZK"}))
        assert rule.extract["doc_currency"] == "CZK"

    def test_int_literal_value_accepted(self) -> None:
        rule = Rule.model_validate(_minimal_rule_data(extract={"doc_amount": 100}))
        assert rule.extract["doc_amount"] == 100

    def test_float_literal_value_accepted(self) -> None:
        rule = Rule.model_validate(_minimal_rule_data(extract={"doc_amount": 99.5}))
        assert rule.extract["doc_amount"] == 99.5

    def test_extract_spec_value_parsed_into_extract_spec(self) -> None:
        rule = Rule.model_validate(
            _minimal_rule_data(
                extract={
                    "doc_number": {
                        "from": "ocr_match",
                        "pattern": r"(\d{10})",
                        "group": 1,
                    }
                }
            )
        )
        assert isinstance(rule.extract["doc_number"], ExtractSpec)
        assert rule.extract["doc_number"].from_ == "ocr_match"

    def test_list_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Rule.model_validate(_minimal_rule_data(extract={"doc_type": [1, 2, 3]}))

    def test_none_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Rule.model_validate(_minimal_rule_data(extract={"doc_type": None}))

    def test_dict_value_with_unknown_extract_field_rejected(self) -> None:
        # A dict value that does not parse as a valid ExtractSpec (extra key)
        # must be rejected, not silently coerced or accepted.
        with pytest.raises(ValidationError):
            Rule.model_validate(_minimal_rule_data(extract={"doc_type": {"unknown_extract_field": "x"}}))

    def test_bool_value_accepted_as_int(self) -> None:
        # Spec allows int values; Python bool is a subclass of int. Document
        # the assumption: bool flows through the int path.
        rule = Rule.model_validate(_minimal_rule_data(extract={"doc_amount": True}))
        assert rule.extract["doc_amount"] is True or rule.extract["doc_amount"] == 1


class TestRuleExtractRequiredForFullRule:
    def test_full_rule_with_empty_extract_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Rule.model_validate(
                {
                    "id": "empty-extract-full",
                    "match": {"ocr_contains": ["foo"]},
                    "extract": {},
                }
            )
        assert "empty-extract-full" in str(exc_info.value)

    def test_full_rule_with_explicit_partial_false_and_empty_extract_rejected(
        self,
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Rule.model_validate(
                {
                    "id": "empty-extract-explicit-full",
                    "partial": False,
                    "match": {"ocr_contains": ["foo"]},
                    "extract": {},
                }
            )
        assert "empty-extract-explicit-full" in str(exc_info.value)

    def test_partial_rule_with_empty_extract_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Rule.model_validate(
                {
                    "id": "empty-extract-partial",
                    "partial": True,
                    "match": {"ocr_contains": ["foo"]},
                    "extract": {},
                }
            )
        assert "empty-extract-partial" in str(exc_info.value)

    def test_partial_rule_with_one_pinned_field_accepted(self) -> None:
        rule = Rule.model_validate(
            {
                "id": "partial-with-pin",
                "partial": True,
                "match": {"ocr_contains": ["foo"]},
                "extract": {"issuer_slug": "x"},
            }
        )
        assert rule.partial is True
        assert rule.extract["issuer_slug"] == "x"


class TestRuleUnknownTopLevelField:
    def test_unknown_top_level_field_rejected_with_rule_id(self) -> None:
        data = _minimal_rule_data(id="typo-rule")
        data["pattren"] = "oops"  # spec's example typo
        with pytest.raises(ValidationError) as exc_info:
            Rule.model_validate(data)
        msg = str(exc_info.value)
        assert "typo-rule" in msg


class TestRuleSpecExamples:
    def test_cez_full_rule_parses(self) -> None:
        rule = Rule.model_validate(CEZ_FULL)
        assert rule.id == "cez-invoice-2024-template"
        assert rule.partial is False
        assert rule.priority == 100
        assert rule.match.ocr_contains == ["IČ: 45274649", "Faktura"]
        assert rule.extract["doc_type"] == "invoice"
        assert isinstance(rule.extract["doc_number"], ExtractSpec)
        assert rule.extract["doc_number"].from_ == "ocr_match"
        assert rule.extract["doc_number"].group == 1
        assert isinstance(rule.extract["doc_date"], ExtractSpec)
        assert rule.extract["doc_date"].transform == "parse_date"
        assert rule.extract["doc_date"].format == "%d.%m.%Y"
        assert isinstance(rule.extract["doc_amount"], ExtractSpec)
        assert rule.extract["doc_amount"].transform == "strip_whitespace_to_int"
        assert rule.extract["doc_currency"] == "CZK"

    def test_cez_partial_rule_parses(self) -> None:
        rule = Rule.model_validate(CEZ_PARTIAL)
        assert rule.id == "cez-fingerprint"
        assert rule.partial is True
        assert rule.match.ocr_contains == ["IČ: 45274649"]
        assert rule.extract["issuer_slug"] == "cez-as"
        assert rule.extract["issuer_display"] == "ČEZ a.s."
        assert rule.extract["doc_language"] == "cs"


# ---------------------------------------------------------------------------
# RuleResult
# ---------------------------------------------------------------------------


class TestRuleResult:
    def test_full_kind_construction(self) -> None:
        r = RuleResult(
            kind="full",
            pinned={"doc_type": "invoice"},
            rule_id="cez-invoice-2024-template",
            rule_version=1,
        )
        assert r.kind == "full"
        assert r.pinned == {"doc_type": "invoice"}
        assert r.rule_id == "cez-invoice-2024-template"
        assert r.rule_version == 1
        assert r.conflicting_rules == []

    def test_partial_kind_construction(self) -> None:
        r = RuleResult(
            kind="partial",
            pinned={"issuer_slug": "cez-as"},
            rule_id="cez-fingerprint",
            rule_version=1,
        )
        assert r.kind == "partial"

    def test_none_kind_construction_with_defaults(self) -> None:
        r = RuleResult(kind="none", rule_id=None, rule_version=None)
        assert r.kind == "none"
        assert r.pinned == {}
        assert r.rule_id is None
        assert r.rule_version is None
        assert r.conflicting_rules == []

    def test_conflict_kind_construction(self) -> None:
        r = RuleResult(
            kind="conflict",
            rule_id=None,
            rule_version=None,
            conflicting_rules=["rule-a", "rule-b"],
        )
        assert r.kind == "conflict"
        assert r.conflicting_rules == ["rule-a", "rule-b"]

    def test_default_pinned_is_empty_dict(self) -> None:
        r = RuleResult(kind="none", rule_id=None, rule_version=None)
        assert r.pinned == {}

    def test_default_conflicting_rules_is_empty_list(self) -> None:
        r = RuleResult(kind="none", rule_id=None, rule_version=None)
        assert r.conflicting_rules == []

    def test_two_results_have_independent_default_pinned(self) -> None:
        a = RuleResult(kind="none", rule_id=None, rule_version=None)
        b = RuleResult(kind="none", rule_id=None, rule_version=None)
        assert a.pinned is not b.pinned

    def test_two_results_have_independent_default_conflicting_rules(self) -> None:
        a = RuleResult(kind="none", rule_id=None, rule_version=None)
        b = RuleResult(kind="none", rule_id=None, rule_version=None)
        assert a.conflicting_rules is not b.conflicting_rules

    def test_is_frozen(self) -> None:
        r = RuleResult(kind="none", rule_id=None, rule_version=None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(r, "kind", "full")


# ---------------------------------------------------------------------------
# SourceMetadata
# ---------------------------------------------------------------------------


class TestSourceMetadata:
    def test_minimal_construction(self) -> None:
        meta = SourceMetadata(source_kind="watch", original_filename="foo.pdf")
        assert meta.source_kind == "watch"
        assert meta.original_filename == "foo.pdf"
        assert meta.email_from is None
        assert meta.email_subject is None
        assert meta.email_date is None

    def test_email_fields_construction(self) -> None:
        meta = SourceMetadata(
            source_kind="email",
            original_filename="invoice.pdf",
            email_from="billing@cez.cz",
            email_subject="Faktura č. 1234567890",
            email_date="2024-01-15",
        )
        assert meta.email_from == "billing@cez.cz"
        assert meta.email_subject == "Faktura č. 1234567890"
        assert meta.email_date == "2024-01-15"

    def test_original_filename_can_be_none(self) -> None:
        meta = SourceMetadata(source_kind="email", original_filename=None)
        assert meta.original_filename is None

    def test_is_frozen(self) -> None:
        meta = SourceMetadata(source_kind="watch", original_filename="foo.pdf")
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(meta, "source_kind", "email")
