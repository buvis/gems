"""Tests for the transforms registry in bim.commands.doc.shared.rules.transforms.

These tests are the spec for the to-be-implemented transforms registry. They
will fail with ImportError until the implementation lands; that is expected.

Assumptions made where the spec was ambiguous:

- ``TRANSFORM_NAMES`` is a ``frozenset[str]`` (immutable). Tests probe both
  the type and the immutability via ``.add()`` raising ``AttributeError``.
- ``apply_transform`` takes ``format`` as a keyword-only argument (the public
  signature in the task spec uses ``*, format=...``).
- The ``"slugify"`` transform delegates to ``bim.commands.doc.shared.naming.slugify``;
  rather than hardcoding the slug for ``"ČEZ Prodej"`` we assert equality with
  the canonical helper. This survives any future tweak to the slug algorithm.
- ``"strip_whitespace_to_decimal"`` accepts both Czech comma decimals
  (``"1 234,56"``) and dot decimals (``"1234.56"``) and returns
  ``decimal.Decimal``.
- ``"strip_whitespace_to_int"`` strips both ASCII spaces and U+00A0 NBSP
  before converting via ``int()``. Inputs that are not numeric after
  stripping propagate ``ValueError`` from ``int()``.
- ``"parse_date"`` requires ``format``; calling it with ``format=None``
  raises ``ValueError`` or ``TypeError`` and the message mentions ``format``
  or ``parse_date`` so the user knows what's missing.
- Single-string transforms (``lowercase``, ``uppercase``, ``strip``,
  ``slugify``, ``strip_whitespace_to_int``, ``strip_whitespace_to_decimal``)
  ignore the ``format`` kwarg silently; passing ``format=None`` does not
  raise.
- The error raised for an unknown transform name is ``ValueError``; the
  message contains both the unknown name and the seven valid names so the
  user sees the fix at a glance.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

# Module under test (will fail to import until the registry is implemented).
from bim.commands.doc.shared import naming
from bim.commands.doc.shared.rules.transforms import (
    TRANSFORM_NAMES,
    TRANSFORMS,
    apply_transform,
)

# ---------------------------------------------------------------------------
# Constants: TRANSFORM_NAMES
# ---------------------------------------------------------------------------


EXPECTED_TRANSFORM_NAMES = {
    "strip_whitespace_to_int",
    "strip_whitespace_to_decimal",
    "parse_date",
    "lowercase",
    "uppercase",
    "strip",
    "slugify",
}


class TestTransformNamesConstant:
    def test_is_frozenset(self) -> None:
        assert isinstance(TRANSFORM_NAMES, frozenset)

    def test_is_immutable(self) -> None:
        # frozenset has no .add(); accessing it must raise AttributeError.
        with pytest.raises(AttributeError):
            getattr(TRANSFORM_NAMES, "add")("new_transform")

    def test_contains_exactly_the_seven_canonical_names(self) -> None:
        assert set(TRANSFORM_NAMES) == EXPECTED_TRANSFORM_NAMES

    def test_has_no_extra_names(self) -> None:
        assert len(TRANSFORM_NAMES) == 7


# ---------------------------------------------------------------------------
# Constants: TRANSFORMS
# ---------------------------------------------------------------------------


class TestTransformsRegistry:
    def test_keys_match_transform_names(self) -> None:
        assert set(TRANSFORMS.keys()) == set(TRANSFORM_NAMES)

    def test_has_seven_entries(self) -> None:
        assert len(TRANSFORMS) == 7

    @pytest.mark.parametrize("name", sorted(EXPECTED_TRANSFORM_NAMES))
    def test_every_value_is_callable(self, name: str) -> None:
        assert callable(TRANSFORMS[name])


# ---------------------------------------------------------------------------
# apply_transform: dispatch
# ---------------------------------------------------------------------------


class TestApplyTransformLowercase:
    def test_lowercase_basic(self) -> None:
        assert apply_transform("lowercase", "HELLO", format=None) == "hello"

    def test_lowercase_mixed_case(self) -> None:
        assert apply_transform("lowercase", "HeLLo WoRLD", format=None) == "hello world"

    def test_lowercase_already_lower_unchanged(self) -> None:
        assert apply_transform("lowercase", "hello", format=None) == "hello"


class TestApplyTransformUppercase:
    def test_uppercase_basic(self) -> None:
        assert apply_transform("uppercase", "hi", format=None) == "HI"

    def test_uppercase_mixed_case(self) -> None:
        assert apply_transform("uppercase", "Hello", format=None) == "HELLO"

    def test_uppercase_already_upper_unchanged(self) -> None:
        assert apply_transform("uppercase", "HI", format=None) == "HI"


class TestApplyTransformStrip:
    def test_strip_outer_whitespace(self) -> None:
        assert apply_transform("strip", "  hi  ", format=None) == "hi"

    def test_strip_preserves_inner_whitespace(self) -> None:
        assert apply_transform("strip", "  a b  ", format=None) == "a b"

    def test_strip_no_whitespace_unchanged(self) -> None:
        assert apply_transform("strip", "x", format=None) == "x"

    def test_strip_ignores_format_argument(self) -> None:
        # Single-string transforms must not error when format is passed.
        assert apply_transform("strip", "  x  ", format=None) == "x"


class TestApplyTransformStripWhitespaceToInt:
    def test_ascii_space_separator(self) -> None:
        assert apply_transform("strip_whitespace_to_int", "4 218", format=None) == 4218

    def test_nbsp_separator(self) -> None:
        # U+00A0 NBSP — Czech invoices often render thousands with NBSP.
        nbsp_value = "4\u00a0218"
        assert apply_transform("strip_whitespace_to_int", nbsp_value, format=None) == 4218

    def test_no_whitespace(self) -> None:
        assert apply_transform("strip_whitespace_to_int", "4218", format=None) == 4218

    def test_returns_int_type_not_bool(self) -> None:
        # bool is a subclass of int; transform must return a true int.
        result = apply_transform("strip_whitespace_to_int", "100", format=None)
        assert isinstance(result, int)
        assert not isinstance(result, bool)


class TestApplyTransformStripWhitespaceToDecimal:
    def test_czech_comma_decimal_with_space_thousands(self) -> None:
        result = apply_transform("strip_whitespace_to_decimal", "1 234,56", format=None)
        assert result == Decimal("1234.56")

    def test_dot_decimal_no_whitespace(self) -> None:
        result = apply_transform("strip_whitespace_to_decimal", "1234.56", format=None)
        assert result == Decimal("1234.56")

    def test_returns_decimal_type(self) -> None:
        result = apply_transform("strip_whitespace_to_decimal", "1 234,56", format=None)
        assert isinstance(result, Decimal)

    def test_nbsp_thousands_separator(self) -> None:
        # NBSP is also commonly used for thousands separators.
        nbsp_value = "1\u00a0234,56"
        result = apply_transform("strip_whitespace_to_decimal", nbsp_value, format=None)
        assert result == Decimal("1234.56")


class TestApplyTransformParseDate:
    def test_czech_dotted_date(self) -> None:
        result = apply_transform("parse_date", "15.11.2024", format="%d.%m.%Y")
        assert result == date(2024, 11, 15)

    def test_returns_date_type(self) -> None:
        result = apply_transform("parse_date", "15.11.2024", format="%d.%m.%Y")
        assert isinstance(result, date)

    def test_iso_format(self) -> None:
        result = apply_transform("parse_date", "2024-11-15", format="%Y-%m-%d")
        assert result == date(2024, 11, 15)


class TestApplyTransformSlugify:
    def test_matches_naming_slugify_for_czech_input(self) -> None:
        # Source of truth: bim.commands.doc.shared.naming.slugify.
        expected = naming.slugify("ČEZ Prodej")
        result = apply_transform("slugify", "ČEZ Prodej", format=None)
        assert result == expected

    def test_matches_naming_slugify_for_ascii_input(self) -> None:
        expected = naming.slugify("Hello World")
        result = apply_transform("slugify", "Hello World", format=None)
        assert result == expected

    def test_returns_str_type(self) -> None:
        result = apply_transform("slugify", "Foo Bar", format=None)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# apply_transform: errors
# ---------------------------------------------------------------------------


class TestApplyTransformUnknownName:
    def test_unknown_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            apply_transform("nonsense", "x", format=None)

    def test_unknown_name_message_contains_the_name(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            apply_transform("nonsense", "x", format=None)
        assert "nonsense" in str(exc_info.value)

    def test_unknown_name_message_lists_valid_names(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            apply_transform("nonsense", "x", format=None)
        msg = str(exc_info.value)
        for valid in EXPECTED_TRANSFORM_NAMES:
            assert valid in msg, f"valid name {valid!r} missing from error: {msg!r}"


class TestApplyTransformPropagatedErrors:
    def test_strip_whitespace_to_int_with_non_numeric_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            apply_transform("strip_whitespace_to_int", "not a number", format=None)


class TestApplyTransformParseDateRequiresFormat:
    def test_parse_date_without_format_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            apply_transform("parse_date", "15.11.2024", format=None)

    def test_parse_date_without_format_message_mentions_format_or_parse_date(self) -> None:
        with pytest.raises((ValueError, TypeError)) as exc_info:
            apply_transform("parse_date", "15.11.2024", format=None)
        msg = str(exc_info.value).lower()
        assert "format" in msg or "parse_date" in msg


class TestApplyTransformIgnoresFormatForSingleStringTransforms:
    def test_strip_with_format_none_ok(self) -> None:
        assert apply_transform("strip", "x", format=None) == "x"

    def test_lowercase_with_format_none_ok(self) -> None:
        assert apply_transform("lowercase", "X", format=None) == "x"

    def test_uppercase_with_format_none_ok(self) -> None:
        assert apply_transform("uppercase", "x", format=None) == "X"

    def test_slugify_with_format_none_ok(self) -> None:
        # Should not raise even though format is None — slugify ignores it.
        result = apply_transform("slugify", "Foo Bar", format=None)
        assert result == naming.slugify("Foo Bar")


# ---------------------------------------------------------------------------
# Direct access via TRANSFORMS dict
# ---------------------------------------------------------------------------


class TestTransformsDirectAccess:
    def test_strip_whitespace_to_decimal_callable(self) -> None:
        result = TRANSFORMS["strip_whitespace_to_decimal"]("1 234,56")
        assert result == Decimal("1234.56")

    def test_strip_callable(self) -> None:
        result = TRANSFORMS["strip"]("  x  ")
        assert result == "x"
