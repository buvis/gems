from __future__ import annotations

import re
from datetime import date

from bim.commands.doc.shared.rules.models import (
    RESERVED_EXTRACT_FIELDS,
    ExtractSpec,
    Rule,
    SourceMetadata,
)
from bim.commands.doc.shared.rules.transforms import apply_transform

__all__ = [
    "apply_extract",
]


def _extract_match_value(spec: ExtractSpec, text: str) -> object | None:
    if spec.pattern is None:
        return None
    match = re.search(spec.pattern, text)
    if match is None:
        return None
    try:
        if spec.groups is not None:
            groups = tuple(match.group(group) for group in spec.groups)
            return _extract_group_value(spec, groups)
        if spec.group is not None:
            return match.group(spec.group)
        return match.group(0)
    except IndexError:
        return None


def _extract_group_value(spec: ExtractSpec, groups: tuple[str, ...]) -> object | None:
    if spec.format != "year-month":
        return None
    try:
        year, month = groups
        return date(int(year), int(month), 1)
    except (TypeError, ValueError):
        return None


def _maybe_transform(spec: ExtractSpec, value: object) -> object | None:
    if spec.transform is None:
        return value
    if not isinstance(value, str):
        return None
    try:
        return apply_transform(spec.transform, value, format=spec.format)
    except (ArithmeticError, TypeError, ValueError):
        return None


def _extract_spec_value(spec: ExtractSpec, ocr_text: str, source: SourceMetadata) -> object | None:
    if spec.from_ == "email_date":
        if source.email_date is None:
            return None
        return _maybe_transform(spec, source.email_date)
    if spec.from_ == "ocr_match":
        text: str | None = ocr_text
    elif spec.from_ == "filename_match":
        text = source.original_filename
    else:
        return None
    if text is None:
        return None
    value = _extract_match_value(spec, text)
    if value is None:
        return None
    return _maybe_transform(spec, value)


def apply_extract(
    rule: Rule,
    ocr_text: str,
    source: SourceMetadata,
    captures: dict[str, list[re.Match[str]]],
) -> dict[str, object] | None:
    _ = captures
    pinned: dict[str, object] = {}

    for field_name, value in rule.extract.items():
        # Defense in depth: load-time validation rejects reserved fields, but
        # callers using ``Rule.model_construct(...)`` bypass that. Surface the
        # programming error loudly here rather than silently writing into a
        # pipeline-owned slot.
        if field_name in RESERVED_EXTRACT_FIELDS:
            raise ValueError(f"extract field {field_name!r} is reserved in rule id {rule.id!r}")
        if isinstance(value, ExtractSpec):
            extracted = _extract_spec_value(value, ocr_text, source)
            if extracted is None:
                return None
            pinned[field_name] = extracted
        else:
            pinned[field_name] = value

    return pinned
