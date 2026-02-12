from datetime import UTC, datetime

import pytest

from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval, safe_eval


class TestSafeEvalAllowed:
    def test_constant(self):
        assert safe_eval("42", {}) == 42

    def test_string_constant(self):
        assert safe_eval("'hello'", {}) == "hello"

    def test_variable(self):
        assert safe_eval("x", {"x": 10}) == 10

    def test_arithmetic(self):
        assert safe_eval("x + y", {"x": 3, "y": 4}) == 7

    def test_len(self):
        assert safe_eval("len(tags)", {"tags": ["a", "b", "c"]}) == 3

    def test_len_none(self):
        assert safe_eval("len(tags)", {"tags": None}) == 0

    def test_comparison(self):
        assert safe_eval("x > 5", {"x": 10}) is True

    def test_boolean_and(self):
        assert safe_eval("x > 0 and y > 0", {"x": 1, "y": 2}) is True

    def test_boolean_or(self):
        assert safe_eval("x > 0 or y > 0", {"x": -1, "y": 2}) is True

    def test_ifexp(self):
        assert safe_eval("'yes' if x else 'no'", {"x": True}) == "yes"
        assert safe_eval("'yes' if x else 'no'", {"x": False}) == "no"

    def test_subscript(self):
        assert safe_eval("tags[0]", {"tags": ["a", "b"]}) == "a"

    def test_upper(self):
        assert safe_eval("upper(name)", {"name": "hello"}) == "HELLO"

    def test_lower(self):
        assert safe_eval("lower(name)", {"name": "HELLO"}) == "hello"

    def test_concat(self):
        assert safe_eval("concat('a', 'b', 'c')", {}) == "abc"

    def test_join(self):
        assert safe_eval("join(', ', tags)", {"tags": ["a", "b"]}) == "a, b"

    def test_substr(self):
        assert safe_eval("substr(name, 0, 3)", {"name": "hello"}) == "hel"

    def test_replace(self):
        assert safe_eval("replace(name, 'l', 'r')", {"name": "hello"}) == "herro"

    def test_year(self):
        dt = datetime(2024, 3, 15, tzinfo=UTC)
        assert safe_eval("year(date)", {"date": dt}) == 2024

    def test_month(self):
        dt = datetime(2024, 3, 15, tzinfo=UTC)
        assert safe_eval("month(date)", {"date": dt}) == 3

    def test_day(self):
        dt = datetime(2024, 3, 15, tzinfo=UTC)
        assert safe_eval("day(date)", {"date": dt}) == 15

    def test_format_date(self):
        dt = datetime(2024, 3, 15, tzinfo=UTC)
        assert safe_eval("format_date(date, '%Y-%m-%d')", {"date": dt}) == "2024-03-15"

    def test_abs(self):
        assert safe_eval("abs(x)", {"x": -5}) == 5

    def test_str_function(self):
        assert safe_eval("str(42)", {}) == "42"

    def test_int_function(self):
        assert safe_eval("int('42')", {}) == 42

    def test_nested_calls(self):
        assert safe_eval("len(join(', ', tags))", {"tags": ["a", "b"]}) == 4


class TestSafeEvalBlocked:
    def test_import(self):
        with pytest.raises(ValueError, match="Unknown variable"):
            safe_eval("__import__('os')", {})

    def test_attribute_access(self):
        with pytest.raises(ValueError, match="Disallowed"):
            safe_eval("x.__class__", {"x": 1})

    def test_lambda(self):
        with pytest.raises(ValueError, match="Disallowed"):
            safe_eval("(lambda: 1)()", {})

    def test_unknown_variable(self):
        with pytest.raises(ValueError, match="Unknown variable"):
            safe_eval("nonexistent", {})

    def test_syntax_error(self):
        with pytest.raises(ValueError, match="Invalid expression"):
            safe_eval("1 +", {})


class TestPythonEval:
    def test_simple_expression(self):
        assert python_eval("1 + 2", {}) == 3

    def test_variable(self):
        assert python_eval("x * 2", {"x": 5}) == 10

    def test_len_builtin(self):
        assert python_eval("len(tags)", {"tags": ["a", "b"]}) == 2

    def test_safe_functions_available(self):
        assert python_eval("upper('hello')", {}) == "HELLO"

    def test_attribute_access(self):
        assert python_eval("title.upper()", {"title": "hello"}) == "HELLO"

    def test_list_comprehension(self):
        assert python_eval("[x * 2 for x in items]", {"items": [1, 2, 3]}) == [2, 4, 6]

    def test_datetime_module(self):
        result = python_eval("datetime.datetime(2024, 1, 1).year", {})
        assert result == 2024

    def test_exec_mode_with_result(self):
        code = "result = sum(x for x in items if x > 2)"
        assert python_eval(code, {"items": [1, 2, 3, 4]}) == 7

    def test_exec_mode_missing_result(self):
        with pytest.raises(ValueError, match="must assign to 'result'"):
            python_eval("x = 1", {"x": 0})

    def test_ternary(self):
        assert python_eval("'yes' if tags else 'no'", {"tags": ["a"]}) == "yes"
        assert python_eval("'yes' if tags else 'no'", {"tags": []}) == "no"

    def test_string_methods(self):
        assert python_eval("title.replace(' ', '-').lower()", {"title": "Hello World"}) == "hello-world"
