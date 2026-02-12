from __future__ import annotations

import ast
import datetime as _datetime_mod
import operator
from collections.abc import Callable
from datetime import datetime
from typing import Any

_SAFE_BINOPS: dict[type, Callable[..., Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_SAFE_UNARYOPS: dict[type, Callable[..., Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_SAFE_CMPOPS: dict[type, Callable[..., Any]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

_SAFE_BOOLOPS: dict[type, Callable[..., Any]] = {
    ast.And: all,
    ast.Or: any,
}


def _safe_len(obj: Any) -> int:
    return len(obj) if obj is not None else 0


def _safe_count(obj: Any, item: Any) -> int:
    if obj is None:
        return 0
    return int(obj.count(item))


def _concat(*args: str) -> str:
    return "".join(str(a) for a in args)


def _join(sep: str, items: Any) -> str:
    if items is None:
        return ""
    return sep.join(str(i) for i in items)


def _substr(s: str, start: int, end: int | None = None) -> str:
    return str(s)[start:end]


def _replace(s: str, old: str, new: str) -> str:
    return str(s).replace(old, new)


def _year(dt: Any) -> int | None:
    return dt.year if isinstance(dt, datetime) else None


def _month(dt: Any) -> int | None:
    return dt.month if isinstance(dt, datetime) else None


def _day(dt: Any) -> int | None:
    return dt.day if isinstance(dt, datetime) else None


def _format_date(dt: Any, fmt: str = "%Y-%m-%d") -> str:
    if isinstance(dt, datetime):
        return dt.strftime(fmt)
    return str(dt) if dt is not None else ""


_SAFE_FUNCTIONS: dict[str, Any] = {
    "len": _safe_len,
    "count": _safe_count,
    "upper": lambda s: str(s).upper(),
    "lower": lambda s: str(s).lower(),
    "concat": _concat,
    "join": _join,
    "substr": _substr,
    "replace": _replace,
    "year": _year,
    "month": _month,
    "day": _day,
    "format_date": _format_date,
    "abs": abs,
    "str": str,
    "int": int,
}

_ALLOWED_NODES = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.IfExp,
    ast.Compare,
    ast.BoolOp,
    ast.Subscript,
    ast.Index,
    ast.Slice,
    ast.Tuple,
    ast.List,
)


def safe_eval(expr: str, variables: dict[str, Any]) -> Any:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        msg = f"Invalid expression: {e}"
        raise ValueError(msg) from e

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES + tuple(_SAFE_BINOPS) + tuple(_SAFE_UNARYOPS) + tuple(_SAFE_CMPOPS) + tuple(_SAFE_BOOLOPS)):
            if not isinstance(node, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
                                     ast.UAdd, ast.USub, ast.Not,
                                     ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
                                     ast.And, ast.Or)):
                msg = f"Disallowed expression node: {type(node).__name__}"
                raise ValueError(msg)

    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCTIONS:
            return _SAFE_FUNCTIONS[node.id]
        if node.id in variables:
            return variables[node.id]
        msg = f"Unknown variable: {node.id}"
        raise ValueError(msg)

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        op_fn = _SAFE_BINOPS.get(type(node.op))
        if op_fn is None:
            msg = f"Unsupported binary op: {type(node.op).__name__}"
            raise ValueError(msg)
        return op_fn(left, right)

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, variables)
        unary_fn = _SAFE_UNARYOPS.get(type(node.op))
        if unary_fn is None:
            msg = f"Unsupported unary op: {type(node.op).__name__}"
            raise ValueError(msg)
        return unary_fn(operand)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, variables)
            cmp_fn = _SAFE_CMPOPS.get(type(op))
            if cmp_fn is None:
                msg = f"Unsupported comparison: {type(op).__name__}"
                raise ValueError(msg)
            if not bool(cmp_fn(left, right)):
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, variables) for v in node.values]
        bool_fn = _SAFE_BOOLOPS.get(type(node.op))
        if bool_fn is None:
            msg = f"Unsupported bool op: {type(node.op).__name__}"
            raise ValueError(msg)
        return bool_fn(values)

    if isinstance(node, ast.Call):
        func = _eval_node(node.func, variables)
        if not callable(func):
            msg = f"Not callable: {func}"
            raise ValueError(msg)
        args = [_eval_node(a, variables) for a in node.args]
        return func(*args)

    if isinstance(node, ast.IfExp):
        test = _eval_node(node.test, variables)
        return _eval_node(node.body, variables) if test else _eval_node(node.orelse, variables)

    if isinstance(node, ast.Subscript):
        value = _eval_node(node.value, variables)
        sl = node.slice
        if isinstance(sl, ast.Slice):
            lower = _eval_node(sl.lower, variables) if sl.lower else None
            upper = _eval_node(sl.upper, variables) if sl.upper else None
            step = _eval_node(sl.step, variables) if sl.step else None
            return value[lower:upper:step]
        idx = _eval_node(sl, variables)
        return value[idx]

    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval_node(e, variables) for e in node.elts]

    msg = f"Unsupported node type: {type(node).__name__}"
    raise ValueError(msg)


def python_eval(code: str, variables: dict[str, Any]) -> Any:
    """Evaluate arbitrary Python code with full builtins.

    Tries single-expression eval first. On SyntaxError falls back to exec
    mode where the code must assign to ``result``.
    """
    ns: dict[str, Any] = {"__builtins__": __builtins__, "datetime": _datetime_mod}
    ns.update(_SAFE_FUNCTIONS)
    ns.update(variables)

    try:
        compiled = compile(code, "<expr>", "eval")
        return eval(compiled, ns)  # noqa: S307
    except SyntaxError:
        compiled = compile(code, "<expr>", "exec")
        exec(compiled, ns)  # noqa: S102
        if "result" not in ns:
            msg = "exec-mode code must assign to 'result'"
            raise ValueError(msg)
        return ns["result"]
