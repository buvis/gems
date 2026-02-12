from __future__ import annotations

import pytest
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval, safe_eval


class TestSafeEval:
    def test_arithmetic(self) -> None:
        result = safe_eval("x + y", {"x": 2, "y": 3})
        assert result == 5

    def test_comparison(self) -> None:
        result = safe_eval("x > 5", {"x": 6})
        assert result is True

    def test_boolean(self) -> None:
        result = safe_eval("x > 0 and y > 0", {"x": 1, "y": 2})
        assert result is True

    def test_function_calls(self) -> None:
        variables = {"items": [1, 2], "name": "Ada", "a": "foo", "b": "bar"}
        assert safe_eval("len(items)", variables) == 2
        assert safe_eval("upper(name)", variables) == "ADA"
        assert safe_eval("concat(a, b)", variables) == "foobar"

    def test_if_expression(self) -> None:
        result = safe_eval("x if x > 0 else 0", {"x": 3})
        assert result == 3

    def test_subscript_index(self) -> None:
        result = safe_eval("items[0]", {"items": ["a", "b"]})
        assert result == "a"

    def test_subscript_slice(self) -> None:
        result = safe_eval("items[1:3]", {"items": [0, 1, 2, 3]})
        assert result == [1, 2]

    def test_disallowed_node(self) -> None:
        with pytest.raises(ValueError, match="Disallowed expression node"):
            safe_eval("obj.attr", {"obj": {"attr": 1}})

    def test_unknown_variable(self) -> None:
        with pytest.raises(ValueError, match="Unknown variable"):
            safe_eval("missing", {})

    def test_invalid_syntax(self) -> None:
        with pytest.raises(ValueError, match="Invalid expression"):
            safe_eval("x +", {"x": 1})


class TestPythonEval:
    def test_simple_expression(self) -> None:
        result = python_eval("x + 1", {"x": 2})
        assert result == 3

    def test_exec_fallback(self) -> None:
        result = python_eval("result = x * 2", {"x": 3})
        assert result == 6

    def test_exec_missing_result(self) -> None:
        with pytest.raises(ValueError, match="exec-mode code must assign to 'result'"):
            python_eval("x = 1", {})

    def test_safe_functions_access(self) -> None:
        result = python_eval("len(items)", {"items": [1, 2, 3]})
        assert result == 3

    def test_datetime_access(self) -> None:
        result = python_eval("datetime.datetime(2024, 1, 2).year", {})
        assert result == 2024
