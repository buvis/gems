from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from bim.commands.doc.shared.rules.models import MatchClauses, Rule, SourceMetadata

__all__ = [
    "MatchResult",
    "evaluate_match",
]


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    captures: dict[str, list[re.Match[str]]]


def _ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _normalize_contains_text(text: str) -> str:
    return _ascii_fold(text).casefold()


def _search_all(patterns: list[str], text: str) -> list[re.Match[str]] | None:
    matches: list[re.Match[str]] = []
    for pattern in patterns:
        match = re.search(pattern, text)
        if match is None:
            return None
        matches.append(match)
    return matches


# Each clause evaluator returns (matched, captures_for_clause).
# matched=False short-circuits the whole rule; captures is None for clauses
# that do not produce regex captures.
ClauseResult = tuple[bool, list[re.Match[str]] | None]


def _eval_ocr_contains(clauses: MatchClauses, ocr_text: str, _source: SourceMetadata) -> ClauseResult:
    if clauses.ocr_contains is None:
        return True, None
    if not ocr_text:
        return False, None
    haystack = _normalize_contains_text(ocr_text)
    if all(_normalize_contains_text(needle) in haystack for needle in clauses.ocr_contains):
        return True, None
    return False, None


def _eval_ocr_matches(clauses: MatchClauses, ocr_text: str, _source: SourceMetadata) -> ClauseResult:
    if clauses.ocr_matches is None:
        return True, None
    matches = _search_all(clauses.ocr_matches, ocr_text)
    if matches is None:
        return False, None
    return True, matches


def _eval_email_from_domain(clauses: MatchClauses, _ocr_text: str, source: SourceMetadata) -> ClauseResult:
    if clauses.email_from_domain is None:
        return True, None
    if source.email_from is None:
        return False, None
    _, separator, domain = source.email_from.casefold().rpartition("@")
    if not separator:
        domain = source.email_from.casefold()
    if any(domain.endswith(candidate.casefold()) for candidate in clauses.email_from_domain):
        return True, None
    return False, None


def _eval_email_subject_contains(clauses: MatchClauses, _ocr_text: str, source: SourceMetadata) -> ClauseResult:
    if clauses.email_subject_contains is None:
        return True, None
    if source.email_subject is None:
        return False, None
    subject = source.email_subject.casefold()
    if all(needle.casefold() in subject for needle in clauses.email_subject_contains):
        return True, None
    return False, None


def _eval_email_subject_matches(clauses: MatchClauses, _ocr_text: str, source: SourceMetadata) -> ClauseResult:
    if clauses.email_subject_matches is None:
        return True, None
    if source.email_subject is None:
        return False, None
    matches = _search_all(clauses.email_subject_matches, source.email_subject)
    if matches is None:
        return False, None
    return True, matches


def _eval_original_filename_matches(clauses: MatchClauses, _ocr_text: str, source: SourceMetadata) -> ClauseResult:
    if clauses.original_filename_matches is None:
        return True, None
    if source.original_filename is None:
        return False, None
    match = re.search(clauses.original_filename_matches, source.original_filename)
    if match is None:
        return False, None
    return True, [match]


# (clause_attr, capture_key, evaluator) — capture_key is None for non-regex clauses.
_CLAUSE_TABLE: tuple[
    tuple[str, str | None, Callable[[MatchClauses, str, SourceMetadata], ClauseResult]],
    ...,
] = (
    ("ocr_contains", None, _eval_ocr_contains),
    ("ocr_matches", "ocr_matches", _eval_ocr_matches),
    ("email_from_domain", None, _eval_email_from_domain),
    ("email_subject_contains", None, _eval_email_subject_contains),
    ("email_subject_matches", "email_subject_matches", _eval_email_subject_matches),
    ("original_filename_matches", "original_filename_matches", _eval_original_filename_matches),
)


def evaluate_match(rule: Rule, ocr_text: str, source: SourceMetadata) -> MatchResult:
    clauses = rule.match
    captures: dict[str, list[re.Match[str]]] = {}
    evaluated = False

    for attr, capture_key, evaluator in _CLAUSE_TABLE:
        if getattr(clauses, attr) is None:
            continue
        evaluated = True
        matched, clause_captures = evaluator(clauses, ocr_text, source)
        if not matched:
            return MatchResult(matched=False, captures={})
        if capture_key is not None and clause_captures is not None:
            captures[capture_key] = clause_captures

    return MatchResult(matched=evaluated, captures=captures)
