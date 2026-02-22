from __future__ import annotations

import pytest
from buvis.pybase.zettel.infrastructure.query.expression_engine import (
    _safe_count,
    _safe_len,
    python_eval,
    safe_eval,
)


class TestSafeEvalUnaryOps:
    def test_unary_positive(self):
        assert safe_eval("+x", {"x": 5}) == 5

    def test_unary_negative(self):
        assert safe_eval("-x", {"x": 5}) == -5

    def test_not_operator(self):
        assert safe_eval("not x", {"x": False}) is True
        assert safe_eval("not x", {"x": True}) is False


class TestSafeEvalArithmetic:
    def test_subtraction(self):
        assert safe_eval("x - y", {"x": 10, "y": 3}) == 7

    def test_multiplication(self):
        assert safe_eval("x * y", {"x": 4, "y": 5}) == 20

    def test_division(self):
        assert safe_eval("x / y", {"x": 10, "y": 4}) == 2.5

    def test_floor_division(self):
        assert safe_eval("x // y", {"x": 10, "y": 3}) == 3

    def test_modulo(self):
        assert safe_eval("x % y", {"x": 10, "y": 3}) == 1

    def test_power(self):
        assert safe_eval("x ** y", {"x": 2, "y": 3}) == 8


class TestSafeEvalComparisons:
    def test_not_equal(self):
        assert safe_eval("x != y", {"x": 1, "y": 2}) is True
        assert safe_eval("x != y", {"x": 1, "y": 1}) is False

    def test_less_than_equal(self):
        assert safe_eval("x <= y", {"x": 3, "y": 3}) is True
        assert safe_eval("x <= y", {"x": 4, "y": 3}) is False

    def test_greater_than_equal(self):
        assert safe_eval("x >= y", {"x": 3, "y": 3}) is True
        assert safe_eval("x >= y", {"x": 2, "y": 3}) is False

    def test_in_operator(self):
        assert safe_eval("x in items", {"x": 2, "items": [1, 2, 3]}) is True
        assert safe_eval("x in items", {"x": 4, "items": [1, 2, 3]}) is False

    def test_not_in_operator(self):
        assert safe_eval("x not in items", {"x": 4, "items": [1, 2, 3]}) is True
        assert safe_eval("x not in items", {"x": 2, "items": [1, 2, 3]}) is False

    def test_chained_comparison(self):
        assert safe_eval("1 < x < 10", {"x": 5}) is True
        assert safe_eval("1 < x < 10", {"x": 15}) is False


class TestSafeFunctions:
    def test_count(self):
        assert safe_eval("count(items, 'a')", {"items": ["a", "b", "a"]}) == 2

    def test_count_none(self):
        assert safe_eval("count(items, 'a')", {"items": None}) == 0

    def test_join_none(self):
        assert safe_eval("join(', ', items)", {"items": None}) == ""

    def test_year_non_datetime(self):
        assert safe_eval("year(x)", {"x": "not a date"}) is None

    def test_month_non_datetime(self):
        assert safe_eval("month(x)", {"x": "not a date"}) is None

    def test_day_non_datetime(self):
        assert safe_eval("day(x)", {"x": "not a date"}) is None

    def test_format_date_none(self):
        assert safe_eval("format_date(x)", {"x": None}) == ""

    def test_format_date_non_datetime(self):
        assert safe_eval("format_date(x)", {"x": "2024-01-01"}) == "2024-01-01"

    def test_abs_function(self):
        assert safe_eval("abs(x)", {"x": -42}) == 42

    def test_str_function(self):
        assert safe_eval("str(x)", {"x": 42}) == "42"

    def test_int_function(self):
        assert safe_eval("int(x)", {"x": "42"}) == 42


class TestSafeEvalTupleAndList:
    def test_list_literal(self):
        result = safe_eval("[1, 2, 3]", {})
        assert result == [1, 2, 3]

    def test_tuple_literal(self):
        result = safe_eval("(1, 2, 3)", {})
        assert result == [1, 2, 3]  # tuples become lists


class TestSafeEvalSubscript:
    def test_slice_with_step(self):
        result = safe_eval("items[::2]", {"items": [0, 1, 2, 3, 4]})
        assert result == [0, 2, 4]


class TestSafeEvalCallErrors:
    def test_call_non_callable(self):
        with pytest.raises(ValueError, match="Not callable"):
            safe_eval("x()", {"x": 42})


class TestHelperFunctions:
    def test_safe_len_none(self):
        assert _safe_len(None) == 0

    def test_safe_len_list(self):
        assert _safe_len([1, 2]) == 2

    def test_safe_count_none(self):
        assert _safe_count(None, "a") == 0

    def test_safe_count_list(self):
        assert _safe_count(["a", "b", "a"], "a") == 2


class TestPythonEvalCaching:
    def test_cache_hit(self):
        """Calling same expression twice uses compile cache."""
        result1 = python_eval("x + 1", {"x": 1})
        result2 = python_eval("x + 1", {"x": 2})
        assert result1 == 2
        assert result2 == 3
