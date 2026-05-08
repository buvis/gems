from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from bim.commands.doc.shared.naming import slugify

__all__ = [
    "TRANSFORMS",
    "TRANSFORM_NAMES",
    "apply_transform",
]


def _strip_whitespace(value: str) -> str:
    return re.sub(r"\s+", "", value)


def strip_whitespace_to_int(value: str) -> int:
    return int(_strip_whitespace(value))


def strip_whitespace_to_decimal(value: str) -> Decimal:
    normalized = _strip_whitespace(value).replace(",", ".")
    return Decimal(normalized)


def parse_date(value: str, *, format: str | None = None) -> date:
    if format is None:
        raise ValueError("format is required for parse_date")
    return datetime.strptime(value, format).date()


def lowercase(value: str) -> str:
    return value.lower()


def uppercase(value: str) -> str:
    return value.upper()


def strip(value: str) -> str:
    return value.strip()


TRANSFORMS: dict[str, Callable[[str], object]] = {
    "strip_whitespace_to_int": strip_whitespace_to_int,
    "strip_whitespace_to_decimal": strip_whitespace_to_decimal,
    "parse_date": parse_date,
    "lowercase": lowercase,
    "uppercase": uppercase,
    "strip": strip,
    "slugify": slugify,
}

TRANSFORM_NAMES = frozenset(TRANSFORMS)


def apply_transform(name: str, value: str, *, format: str | None) -> object:
    if name not in TRANSFORMS:
        raise ValueError(f"unknown transform: {name!r}; valid: {sorted(TRANSFORM_NAMES)}")
    if name == "parse_date":
        return parse_date(value, format=format)
    return TRANSFORMS[name](value)
