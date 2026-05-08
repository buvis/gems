from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "RESERVED_EXTRACT_FIELDS",
    "ExtractSpec",
    "MatchClauses",
    "Rule",
    "RuleResult",
    "SourceMetadata",
]

_TRANSFORMS = {
    "strip_whitespace_to_int",
    "strip_whitespace_to_decimal",
    "parse_date",
    "lowercase",
    "uppercase",
    "strip",
    "slugify",
}

# Field names rule authors cannot set: the pipeline / writer owns these.
# Enforced at load time by Rule._validate_extract_keys; re-checked at runtime
# in apply_extract so model_construct() callers cannot bypass the guard.
RESERVED_EXTRACT_FIELDS = frozenset(
    {
        "extraction_method",
        "id",
        "ingest_date",
        "ingest_source",
        "file_path",
        "file_sha256",
    }
)

_ALLOWED_EXTRACT_FIELDS = {
    "issuer_slug",
    "issuer_display",
    "doc_type",
    "doc_number",
    "doc_date",
    "doc_amount",
    "doc_currency",
    "doc_language",
}


def _compile_regex(pattern: str) -> None:
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc


class MatchClauses(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ocr_contains: list[str] | None = None
    ocr_matches: list[str] | None = None
    email_from_domain: list[str] | None = None
    email_subject_contains: list[str] | None = None
    email_subject_matches: list[str] | None = None
    original_filename_matches: str | None = None

    @field_validator(
        "ocr_contains",
        "ocr_matches",
        "email_from_domain",
        "email_subject_contains",
        "email_subject_matches",
        mode="before",
    )
    @classmethod
    def _string_to_list(cls, v: object) -> object:
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("ocr_matches", "email_subject_matches")
    @classmethod
    def _regex_lists_compile(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for pattern in v:
            _compile_regex(pattern)
        return v

    @field_validator("original_filename_matches")
    @classmethod
    def _filename_regex_compiles(cls, v: str | None) -> str | None:
        if v is not None:
            _compile_regex(v)
        return v


class ExtractSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    from_: Literal["ocr_match", "filename_match", "email_date"] | None = Field(default=None, alias="from")
    pattern: str | None = None
    group: int | None = None
    groups: list[int] | None = None
    transform: str | None = None
    format: str | None = None

    @field_validator("pattern")
    @classmethod
    def _pattern_compiles(cls, v: str | None) -> str | None:
        if v is not None:
            _compile_regex(v)
        return v

    @field_validator("groups")
    @classmethod
    def _groups_are_non_empty_and_non_negative(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if not v:
            raise ValueError("groups must be non-empty")
        for group in v:
            if group < 0:
                raise ValueError("groups must contain only non-negative ints")
        return v

    @field_validator("transform")
    @classmethod
    def _transform_is_known(cls, v: str | None) -> str | None:
        if v is not None and v not in _TRANSFORMS:
            raise ValueError(f"unknown transform {v!r}")
        return v

    @model_validator(mode="after")
    def _verify_constraints(self) -> ExtractSpec:
        if self.from_ is None:
            raise ValueError("from must be one of 'ocr_match', 'filename_match', or 'email_date'")
        if self.from_ in {"ocr_match", "filename_match"} and self.pattern is None:
            raise ValueError(f"pattern is required when from is {self.from_!r}")
        if self.from_ == "email_date" and (
            self.pattern is not None or self.group is not None or self.groups is not None
        ):
            raise ValueError("pattern, group, and groups are forbidden when from is 'email_date'")
        if self.group is not None and self.groups is not None:
            raise ValueError("group and groups are mutually exclusive")
        return self


ExtractValue = ExtractSpec | str | int | float


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    version: int = 1
    priority: int = 50
    enabled: bool = True
    partial: bool = False
    match: MatchClauses
    extract: dict[str, ExtractValue]
    confidence: float = 1.0
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _extra_fields_include_rule_id(cls, data: object) -> object:
        if isinstance(data, dict):
            extra = set(data) - set(cls.model_fields)
            if extra:
                rule_id = data.get("id", "<unknown>")
                raise ValueError(f"rule id {rule_id!r} has unknown top-level fields: {sorted(extra)}")
        return data

    @field_validator("id")
    @classmethod
    def _id_well_formed(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("id must be non-empty")
        # The pipeline composes ``extraction_method`` as
        # ``rule:<id>:v<n>`` / ``rule+llm:<id>:v<n>`` and the writer
        # validates against ``_EXTRACTION_METHOD_REGEX`` which uses
        # ``:`` as a delimiter (``rule:[^:]+:v\d+``). An id containing
        # ``:`` would slip past load time and fail at zettel-write time
        # with an opaque regex mismatch, so reject early.
        if ":" in v:
            raise ValueError(f"rule id {v!r} must not contain ':' (reserved as extraction_method delimiter)")
        return v

    @field_validator("version")
    @classmethod
    def _version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version must be >= 1")
        return v

    @field_validator("extract", mode="before")
    @classmethod
    def _validate_extract_keys(cls, v: object, info: Any) -> object:
        if not isinstance(v, dict):
            return v
        rule_id = info.data.get("id", "<unknown>")
        for key in v:
            if key in RESERVED_EXTRACT_FIELDS:
                raise ValueError(f"extract field {key!r} is reserved in rule id {rule_id!r}")
        for key in v:
            if key not in _ALLOWED_EXTRACT_FIELDS:
                raise ValueError(f"extract field {key!r} is not allowed in rule id {rule_id!r}")
        return v

    @model_validator(mode="after")
    def _verify_rule(self) -> Rule:
        if not any(value is not None for value in self.match.model_dump().values()):
            raise ValueError(f"rule id {self.id!r} must define at least one match clause")
        if not self.extract:
            raise ValueError(f"rule id {self.id!r} must define at least one extract field")
        return self


@dataclass(frozen=True)
class RuleResult:
    kind: Literal["full", "partial", "none", "conflict"]
    rule_id: str | None
    rule_version: int | None
    pinned: dict[str, object] = field(default_factory=dict)
    conflicting_rules: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourceMetadata:
    source_kind: str
    original_filename: str | None
    email_from: str | None = None
    email_subject: str | None = None
    email_date: str | None = None
